"""Runs the Network Expert over benchmark questions × repetitions and stores every raw run
(docs/evaluating-resto.md §4.2).

One JSON line per (question, repetition) in `out_file`: the answer, the promotion outcome, the tool
calls, the full evidence ledger, tokens and estimated cost. Scoring happens later from these lines
(`report.py`), so a scoring rule can change without paying for the runs again.

- **Resumable**: a (question, repetition) already in `out_file` is skipped.
- **Cost cap**: with `max_cost_usd`, no new run starts once the estimated spend reaches it.
- **Crashes** (e.g. an API error) are logged and not written, so the next invocation retries them.
- **Workers** each get their own `Environment` (repositories + network query): a SQLite connection
  and a sumolib network are not shared across threads.
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

from eval.expert_benchmark.bank import BenchmarkQuestion
from resto.adapters.llm.agents.expert import run_expert
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import ResultRepository, ScenarioRepository
from resto.application.schemas import adapter_for
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.ask_expert import (
    ExpertAnswerRejected,
    ExpertRunFailed,
    ask_expert,
)
from resto.domain.value_objects.expert_answer import ExpertAnswer

PriceFn = Callable[[int, int], float | None]


@dataclass(frozen=True, slots=True)
class Environment:
    results: ResultRepository
    scenarios: ScenarioRepository
    query: NetworkQuery
    close: Callable[[], None] = lambda: None


EnvironmentFactory = Callable[[], Environment]


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


def run_benchmark(
    questions: Sequence[BenchmarkQuestion],
    *,
    repetitions: int,
    agent: ToolAgent,
    budget: Budget,
    environment: EnvironmentFactory,
    out_file: Path,
    model: str,
    price: PriceFn = lambda input_tokens, output_tokens: None,
    workers: int = 1,
    max_cost_usd: float | None = None,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    if repetitions < 1 or workers < 1:
        raise ValueError("repetitions and workers must be >= 1")
    done = {(r["question_id"], r["repetition"]) for r in load_records(out_file)}
    jobs = [
        (q, rep)
        for q in questions
        for rep in range(1, repetitions + 1)
        if (q.id, rep) not in done
    ]
    out_file.parent.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    local = threading.local()
    environments: list[Environment] = []
    counters = {"ran": 0, "budget": 0, "crashed": 0}
    spent = [0.0]

    def env() -> Environment:
        if not hasattr(local, "env"):
            local.env = environment()
            with lock:
                environments.append(local.env)
        return local.env  # type: ignore[no-any-return]

    def run_one(question: BenchmarkQuestion, repetition: int) -> None:
        with lock:
            if max_cost_usd is not None and spent[0] >= max_cost_usd:
                counters["budget"] += 1
                return
        try:
            record = _run_once(question, repetition, agent, budget, env(), model, price)
        except Exception as exc:  # an API/network failure must not stop the other runs
            with lock:
                counters["crashed"] += 1
            log(f"CRASH {question.id} rep {repetition}: {exc!r}")
            return
        with lock:
            with out_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
            counters["ran"] += 1
            spent[0] += record["cost_usd"] or 0.0
            outcome = "accepted" if record["rejection"] is None else "rejected"
            log(
                f"[{counters['ran']}/{len(jobs)}] {question.id} rep {repetition}: "
                f"{record['stop_reason']}, {outcome}, ${record['cost_usd'] or 0:.4f} "
                f"(total ${spent[0]:.3f})"
            )

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in [pool.submit(run_one, q, rep) for q, rep in jobs]:
                future.result()
    finally:
        for environment_ in environments:
            environment_.close()

    return RunOutcome(
        ran=counters["ran"],
        skipped_done=len(questions) * repetitions - len(jobs),
        skipped_budget=counters["budget"],
        crashed=counters["crashed"],
        cost_usd=spent[0],
    )


def _run_once(
    question: BenchmarkQuestion,
    repetition: int,
    agent: ToolAgent,
    budget: Budget,
    env: Environment,
    model: str,
    price: PriceFn,
) -> dict[str, Any]:
    task = question.to_task()
    ledger = EvidenceLedger()
    started = time.monotonic()
    run = run_expert(
        task,
        agent,
        budget,
        query=env.query,
        results=env.results,
        scenarios=env.scenarios,
        notes=None,
        ledger=ledger,
    )
    elapsed = time.monotonic() - started
    rejection: str | None = None
    try:
        ask_expert(task, run, ledger, query=env.query)
    except (ExpertRunFailed, ExpertAnswerRejected) as exc:
        rejection = str(exc)
    return {
        "question_id": question.id,
        "repetition": repetition,
        "model": model,
        "stop_reason": run.stop_reason.value,
        "rejection": rejection,
        "answer": None
        if run.output is None
        else adapter_for(ExpertAnswer).dump_python(run.output, mode="json"),
        "tool_calls": [
            {"name": c.name, "arguments": dict(c.arguments), "result_summary": c.result_summary}
            for c in run.tool_calls
        ],
        "ledger": [
            {"ref": e.ref, "tool": e.tool, "arguments": dict(e.arguments), "result": e.result}
            for e in ledger.entries
        ],
        "input_tokens": run.usage.input_tokens,
        "output_tokens": run.usage.output_tokens,
        "cost_usd": price(run.usage.input_tokens, run.usage.output_tokens),
        "elapsed_s": round(elapsed, 2),
    }
