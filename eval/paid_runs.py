"""One loop and one cost policy meant to be shared by every eval runner that spends OpenRouter
credit (CLAUDE.md "LLM provider & cost policy"; refactor-paid-runs decisions 4-9). `eval/
expert_benchmark` is migrated onto it; `eval/parser_benchmark` and `eval/hygiene_probes` still run
their own pre-refactor loop and are migrated separately (refactor-paid-runs, ticket 04).

A benchmark supplies its job list, how to turn one job into a JSON record (`run_one`), and how to
key a job for resume (`key`/`record_key`); `run_paid_jobs` owns resume-by-key, the JSONL append,
counters, crash logging, the worker pool and the cost policy: a mandatory cap, the pre-run $1 and
cap gates, and a per-worker in-flight reservation so `workers > 1` cannot start more than the cap
allows.

`run_one`'s record must carry `ESTIMATED_COST_KEY` (float) and `REAL_COST_KEY` (float | None) next
to whatever fields the benchmark itself needs — the cap and `RunOutcome` are computed from those two
alone.
"""

from __future__ import annotations

import argparse
import json
import threading
from collections.abc import Callable, Hashable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from resto.adapters.llm.pricing import UnknownModelError, estimate_cost_usd

__all__ = [
    "ESTIMATED_COST_KEY",
    "REAL_COST_KEY",
    "CostCapExceededError",
    "CostPolicy",
    "OverOneDollarError",
    "RunOutcome",
    "UnknownModelError",
    "add_paid_run_arguments",
    "load_records",
    "require_cap",
    "run_paid_jobs",
]

J = TypeVar("J")
PriceFn = Callable[[int, int], float]

ESTIMATED_COST_KEY = "estimated_cost_usd"
REAL_COST_KEY = "real_cost_usd"

ONE_DOLLAR_RULE = (
    'CLAUDE.md "LLM provider & cost policy": a development run estimated above $1 stops and asks '
    "first, pass --approved-over-1usd once the maintainer has said yes; a measurement run waits "
    "for a validation pass whatever its price, and --approved-over-1usd never authorizes running "
    "one early"
)


class OverOneDollarError(ValueError):
    """The estimate exceeds $1 and `--approved-over-1usd` was not passed."""


class CostCapExceededError(ValueError):
    """The estimate for the pending jobs exceeds `CostPolicy.max_cost_usd`."""


@dataclass(frozen=True, slots=True)
class CostPolicy:
    """Prices a run before it starts, from tokens the benchmark declares per job (decision 5), and
    gates it against the $1 rule (decision 6) and the cap (decision 7)."""

    model: str
    price: PriceFn
    input_tokens_per_job: int
    output_tokens_per_job: int
    max_cost_usd: float
    approved_over_1usd: bool = False

    @classmethod
    def for_model(
        cls,
        model: str,
        *,
        input_tokens_per_job: int,
        output_tokens_per_job: int,
        max_cost_usd: float,
        approved_over_1usd: bool = False,
    ) -> CostPolicy:
        """Prices `model` from `config/prices.toml`; raises `UnknownModelError` for one absent
        from it, before anything is spent."""
        return cls(
            model=model,
            price=lambda input_tokens, output_tokens: estimate_cost_usd(
                model, input_tokens, output_tokens
            ),
            input_tokens_per_job=input_tokens_per_job,
            output_tokens_per_job=output_tokens_per_job,
            max_cost_usd=max_cost_usd,
            approved_over_1usd=approved_over_1usd,
        )

    @property
    def per_job_estimate_usd(self) -> float:
        return self.price(self.input_tokens_per_job, self.output_tokens_per_job)

    def check(self, n_jobs: int) -> float:
        """Raises `OverOneDollarError`/`CostCapExceededError` if the estimate for `n_jobs` pending
        jobs is refused; returns the estimate otherwise."""
        estimate = self.per_job_estimate_usd * n_jobs
        if estimate > 1.0 and not self.approved_over_1usd:
            raise OverOneDollarError(
                f"estimated ${estimate:.2f} for {n_jobs} jobs — {ONE_DOLLAR_RULE}"
            )
        if estimate > self.max_cost_usd:
            raise CostCapExceededError(
                f"estimated ${estimate:.2f} for {n_jobs} jobs exceeds the ${self.max_cost_usd:.2f} "
                "cap — raise the cap or shrink the run"
            )
        return estimate


@dataclass(frozen=True, slots=True)
class RunOutcome:
    ran: int
    skipped_done: int
    skipped_budget: int
    crashed: int
    estimated_cost_usd: float
    real_cost_usd: float | None


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def add_paid_run_arguments(parser: argparse.ArgumentParser) -> None:
    """`--max-cost-usd`, `--approved-over-1usd`, `--workers`, shared by every paid-run CLI. The cap
    is parsed as optional here (`--dry-run`/`--report-only` need none); a caller about to spend
    enforces it with `require_cap`."""
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="cap in USD for this invocation; required unless --dry-run/--report-only",
    )
    parser.add_argument(
        "--approved-over-1usd",
        action="store_true",
        help="required for an estimate above $1, only after the maintainer has said yes",
    )
    parser.add_argument("--workers", type=int, default=1)


def require_cap(parser: argparse.ArgumentParser, max_cost_usd: float | None) -> float:
    """Enforces decision 4 (cap mandatory) for a caller that is about to spend; exits via
    `parser.error` (argparse convention) when it is missing."""
    if max_cost_usd is None:
        parser.error("--max-cost-usd is required (omit only for --dry-run/--report-only)")
    assert max_cost_usd is not None  # parser.error raises SystemExit; this satisfies mypy
    return max_cost_usd


def run_paid_jobs(
    jobs: Sequence[J],
    *,
    run_one: Callable[[J], dict[str, Any]],
    key: Callable[[J], Hashable],
    record_key: Callable[[dict[str, Any]], Hashable],
    cost_policy: CostPolicy,
    out_file: Path,
    workers: int = 1,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    if workers < 1:
        raise ValueError("workers must be >= 1")
    done = {record_key(r) for r in load_records(out_file)}
    pending = [job for job in jobs if key(job) not in done]
    out_file.parent.mkdir(parents=True, exist_ok=True)

    cost_policy.check(len(pending))
    per_job_estimate = cost_policy.per_job_estimate_usd
    cap = cost_policy.max_cost_usd

    lock = threading.Lock()
    counters = {"ran": 0, "budget": 0, "crashed": 0}
    state = {"spent": 0.0, "in_flight": 0, "real_total": 0.0, "real_known": True}

    def reserve() -> bool:
        with lock:
            state["in_flight"] += 1
            if state["spent"] + state["in_flight"] * per_job_estimate >= cap:
                state["in_flight"] -= 1
                return False
            return True

    def worker(job: J) -> None:
        if not reserve():
            with lock:
                counters["budget"] += 1
            return
        try:
            record = run_one(job)
        except Exception as exc:  # an API/network failure must not stop the other jobs
            with lock:
                state["in_flight"] -= 1
                counters["crashed"] += 1
            log(f"CRASH {key(job)!r}: {exc!r}")
            return
        estimated = float(record[ESTIMATED_COST_KEY])
        real = record.get(REAL_COST_KEY)
        with lock:
            state["in_flight"] -= 1
            state["spent"] += estimated
            if real is None:
                state["real_known"] = False
            else:
                state["real_total"] += real
            counters["ran"] += 1
            with out_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
            log(
                f"[{counters['ran']}/{len(pending)}] {key(job)!r}: "
                f"est ${estimated:.4f} (total est ${state['spent']:.3f})"
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(worker, job) for job in pending]:
            future.result()

    return RunOutcome(
        ran=counters["ran"],
        skipped_done=len(jobs) - len(pending),
        skipped_budget=counters["budget"],
        crashed=counters["crashed"],
        estimated_cost_usd=state["spent"],
        real_cost_usd=state["real_total"] if state["real_known"] else None,
    )
