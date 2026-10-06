"""Runs the Network Expert over benchmark questions × repetitions and stores every raw run
(eval/README.md §4.2). One JSON line per (question, repetition, mode) in `out_file`: the
Expert version, the answer, the promotion outcome, the tool calls, the per-step trace, the full
evidence ledger, tokens and estimated/real cost. Scoring happens later from these lines
(`report.py`), so a scoring rule can change without paying for the runs again.

Resume, the cost policy and the worker pool live in `eval.paid_runs.run_paid_jobs`
(refactor-paid-runs, ticket 03); this module supplies only the job, its resume key, and how to run
one (`_run_once`). **Workers** each get their own `Environment` (repositories + network query): a
SQLite connection and a sumolib network are not shared across threads.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from eval.expert_benchmark.bank import BenchmarkQuestion
from eval.fixed_network_query_loader import FixedNetworkQueryLoader
from eval.paid_runs import ESTIMATED_COST_KEY, REAL_COST_KEY, CostPolicy, RunOutcome, run_paid_jobs
from resto.adapters.llm.agents.expert import EXPERT_VERSION, run_expert
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import ResultRepository, ScenarioRepository
from resto.application.promotion import DraftRejected, RunWithoutDraft
from resto.application.schemas import adapter_for
from resto.application.tools.expert import EvidenceLedger, expert_context
from resto.application.use_cases.ask_expert import ask_expert
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.question import Mode


@dataclass(frozen=True, slots=True)
class Environment:
    results: ResultRepository
    scenarios: ScenarioRepository
    query: NetworkQuery
    close: Callable[[], None] = lambda: None


EnvironmentFactory = Callable[[], Environment]
Job = tuple[BenchmarkQuestion, int, Mode]


def _key(job: Job) -> tuple[str, int, str]:
    question, repetition, mode = job
    return (question.id, repetition, mode.value)


def _record_key(record: dict[str, Any]) -> tuple[str, int, str]:
    return (record["question_id"], record["repetition"], record.get("mode", Mode.FORCED.value))


def run_benchmark(
    questions: Sequence[BenchmarkQuestion],
    *,
    repetitions: int,
    agent: ToolAgent,
    budget: Budget,
    environment: EnvironmentFactory,
    out_file: Path,
    cost_policy: CostPolicy,
    modes: Sequence[Mode] = (Mode.FORCED,),
    workers: int = 1,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    jobs: list[Job] = [
        (question, rep, mode)
        for mode in modes
        for question in questions
        for rep in range(1, repetitions + 1)
    ]

    lock = threading.Lock()
    local = threading.local()
    environments: list[Environment] = []

    def env() -> Environment:
        if not hasattr(local, "env"):
            local.env = environment()
            with lock:
                environments.append(local.env)
        return local.env  # type: ignore[no-any-return]

    def run_one(job: Job) -> dict[str, Any]:
        question, repetition, mode = job
        return _run_once(question, repetition, agent, budget, env(), cost_policy, mode)

    try:
        return run_paid_jobs(
            jobs,
            run_one=run_one,
            key=_key,
            record_key=_record_key,
            cost_policy=cost_policy,
            out_file=out_file,
            workers=workers,
            log=log,
        )
    finally:
        for environment_ in environments:
            environment_.close()


def _run_once(
    question: BenchmarkQuestion,
    repetition: int,
    agent: ToolAgent,
    budget: Budget,
    env: Environment,
    cost_policy: CostPolicy,
    mode: Mode,
) -> dict[str, Any]:
    task = question.to_task(mode=mode)
    ledger = EvidenceLedger()
    started = time.monotonic()
    loader = FixedNetworkQueryLoader(env.query)
    context = expert_context(
        task, loader=loader, results=env.results, scenarios=env.scenarios, notes=None
    )
    run = run_expert(task, agent, budget, context, ledger)
    elapsed = time.monotonic() - started
    rejection: str | None = None
    try:
        ask_expert(task, run, ledger, loader=loader)
    except (RunWithoutDraft, DraftRejected) as exc:
        rejection = str(exc)
    return {
        "question_id": question.id,
        "repetition": repetition,
        "mode": task.mode.value,
        "model": cost_policy.model,
        "expert_version": EXPERT_VERSION,
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
        "steps": [asdict(step) for step in run.steps],
        "input_tokens": run.usage.input_tokens,
        "output_tokens": run.usage.output_tokens,
        ESTIMATED_COST_KEY: cost_policy.price(run.usage.input_tokens, run.usage.output_tokens),
        REAL_COST_KEY: run.usage.cost_usd,
        "elapsed_s": round(elapsed, 2),
    }
