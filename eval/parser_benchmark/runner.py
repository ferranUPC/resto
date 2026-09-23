"""Runs the Input Parser over request-bank requests × repetitions and stores every raw run
(E5.1; docs/evaluating-resto.md §5).

One JSON line per (request, repetition) in `out_file`: the model, the parser version, the parsed
`Question` (or why there is none), the per-step trace, tokens and estimated cost. Scoring happens
later from these lines (`report.py`), so a scoring rule can change without paying for the runs
again.

- **Resumable**: a (request, repetition) already in `out_file` is skipped.
- **Cost cap**: with `max_cost_usd`, no new run starts once the estimated spend reaches it.
- **Crashes** (e.g. an API error) are logged and not written, so the next invocation retries them.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.request_bank.bank import BankRequest
from resto.adapters.llm.agents.input_parser import PARSER_VERSION, InputParserPort
from resto.application.ports.llm import AgentRun, Budget, ToolAgent
from resto.application.schemas import adapter_for
from resto.domain.value_objects.question import Question

PriceFn = Callable[[int, int], float | None]


@dataclass(frozen=True, slots=True)
class RunOutcome:
    ran: int
    skipped_done: int
    skipped_budget: int
    crashed: int
    cost_usd: float


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _record(
    request: BankRequest, repetition: int, run: AgentRun[Question], model: str, price: PriceFn,
    seconds: float,
) -> dict[str, Any]:
    question = run.output
    failure = None
    if question is None:
        failure = run.tool_calls[-1].result_summary if run.tool_calls else "no submit_output call"
    usage = run.usage
    return {
        "request_id": request.id,
        "repetition": repetition,
        "model": model,
        "parser_version": PARSER_VERSION,
        "stop_reason": run.stop_reason.value,
        "question": None if question is None else adapter_for(Question).dump_python(
            question, mode="json"
        ),
        "failure": failure,
        "steps": [
            {"finish_reason": s.finish_reason, "tool_calls": list(s.tool_calls),
             "output_tokens": s.output_tokens}
            for s in run.steps
        ],
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": price(usage.input_tokens, usage.output_tokens),
        "seconds": round(seconds, 2),
    }


def run_benchmark(
    requests: Sequence[BankRequest],
    *,
    repetitions: int,
    agent: ToolAgent,
    budget: Budget,
    out_file: Path,
    model: str,
    price: PriceFn = lambda input_tokens, output_tokens: None,
    workers: int = 1,
    max_cost_usd: float | None = None,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    if repetitions < 1 or workers < 1:
        raise ValueError("repetitions and workers must be >= 1")
    done = {(r["request_id"], r["repetition"]) for r in load_records(out_file)}
    jobs = [
        (request, rep)
        for request in requests
        for rep in range(1, repetitions + 1)
        if (request.id, rep) not in done
    ]
    out_file.parent.mkdir(parents=True, exist_ok=True)
    parser = InputParserPort(agent, budget)

    lock = threading.Lock()
    counters = {"ran": 0, "budget": 0, "crashed": 0}
    spent = [0.0]

    def run_one(request: BankRequest, repetition: int) -> None:
        with lock:
            if max_cost_usd is not None and spent[0] >= max_cost_usd:
                counters["budget"] += 1
                return
        started = time.monotonic()
        try:
            run = parser.parse(request.text)
        except Exception as exc:  # an API/network failure must not stop the other runs
            with lock:
                counters["crashed"] += 1
            log(f"CRASH {request.id} rep {repetition}: {exc!r}")
            return
        record = _record(request, repetition, run, model, price, time.monotonic() - started)
        with lock:
            with out_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            counters["ran"] += 1
            spent[0] += record["cost_usd"] or 0.0
            log(
                f"[{counters['ran']}/{len(jobs)}] {request.id} rep {repetition}: "
                f"{record['stop_reason']}, ${record['cost_usd'] or 0:.4f} (total ${spent[0]:.3f})"
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(run_one, request, rep) for request, rep in jobs]:
            future.result()

    return RunOutcome(
        ran=counters["ran"],
        skipped_done=len(requests) * repetitions - len(jobs),
        skipped_budget=counters["budget"],
        crashed=counters["crashed"],
        cost_usd=spent[0],
    )
