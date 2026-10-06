"""Runs the Input Parser over request-bank requests × repetitions and stores every raw run
(E5.1; eval/decisions-log.md,).

One JSON line per (request, repetition) in `out_file`: the model, the parser version, the parsed
`Question` (or why there is none), the per-step trace, tokens and estimated/real cost. Scoring
happens later from these lines (`report.py`), so a scoring rule can change without paying for the
runs again.

Resume, the cost policy and the worker pool live in `eval.paid_runs.run_paid_jobs`
(refactor-paid-runs, ticket 04); this module supplies only the job, its resume key, and how to run
one (`_run_once`).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from eval.paid_runs import ESTIMATED_COST_KEY, REAL_COST_KEY, CostPolicy, RunOutcome, run_paid_jobs
from eval.request_bank.bank import BankRequest
from resto.adapters.llm.agents.input_parser import PARSER_VERSION, InputParserPort
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.schemas import adapter_for
from resto.domain.value_objects.question import Question

Job = tuple[BankRequest, int]


def _key(job: Job) -> tuple[str, int]:
    request, repetition = job
    return (request.id, repetition)


def _record_key(record: dict[str, Any]) -> tuple[str, int]:
    return (record["request_id"], record["repetition"])


def run_benchmark(
    requests: Sequence[BankRequest],
    *,
    repetitions: int,
    agent: ToolAgent,
    budget: Budget,
    out_file: Path,
    cost_policy: CostPolicy,
    workers: int = 1,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    jobs: list[Job] = [(request, rep) for request in requests for rep in range(1, repetitions + 1)]
    parser = InputParserPort(agent, budget)

    def run_one(job: Job) -> dict[str, Any]:
        request, repetition = job
        return _run_once(request, repetition, parser, cost_policy)

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


def _run_once(
    request: BankRequest, repetition: int, parser: InputParserPort, cost_policy: CostPolicy
) -> dict[str, Any]:
    started = time.monotonic()
    run = parser.parse(request.text)
    elapsed = time.monotonic() - started
    question = run.output
    failure = None
    if question is None:
        failure = run.tool_calls[-1].result_summary if run.tool_calls else "no submit_output call"
    return {
        "request_id": request.id,
        "repetition": repetition,
        "model": cost_policy.model,
        "parser_version": PARSER_VERSION,
        "stop_reason": run.stop_reason.value,
        "question": None
        if question is None
        else adapter_for(Question).dump_python(question, mode="json"),
        "failure": failure,
        "steps": [
            {
                "finish_reason": s.finish_reason,
                "tool_calls": list(s.tool_calls),
                "output_tokens": s.output_tokens,
            }
            for s in run.steps
        ],
        "input_tokens": run.usage.input_tokens,
        "output_tokens": run.usage.output_tokens,
        ESTIMATED_COST_KEY: cost_policy.price(run.usage.input_tokens, run.usage.output_tokens),
        REAL_COST_KEY: run.usage.cost_usd,
        "seconds": round(elapsed, 2),
    }
