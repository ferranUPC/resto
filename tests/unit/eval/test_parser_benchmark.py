from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import pytest
from eval.paid_runs import CostCapExceededError, CostPolicy, load_records
from eval.parser_benchmark import run as cli
from eval.parser_benchmark.report import (
    failed_fields,
    render_markdown,
    score_records,
    summarize_run,
)
from eval.parser_benchmark.runner import run_benchmark
from eval.request_bank.bank import BankRequest, bank_requests
from eval.request_bank.concepts import CONCEPTS

from resto.adapters.llm.agents.input_parser import PARSER_VERSION, SYSTEM_PROMPT
from resto.application.ports.llm import AgentRun, AgentTask, Budget, StopReason, Tool
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import Usage

T = TypeVar("T")

BUDGET = Budget(max_steps=2, max_tokens=2048, max_seconds=60.0)


@dataclass
class GoldAgent:
    """Answers each request with its gold, except the requests in `fail`, which get no Question;
    an ambiguous gold gets a Question with one ambiguity."""

    requests: Sequence[BankRequest]
    fail: frozenset[str] = frozenset()
    crash: frozenset[str] = frozenset()
    seen: list[str] = field(default_factory=list)

    def run(
        self, task: AgentTask, tools: Sequence[Tool], output: type[T], budget: Budget
    ) -> AgentRun[Any]:
        text = task.input["request"]
        request = next(r for r in self.requests if r.text == text)
        self.seen.append(request.id)
        if request.id in self.crash:
            raise ConnectionError("503")
        usage = Usage(input_tokens=1000, output_tokens=100)
        if request.id in self.fail:
            return AgentRun(None, (), usage, StopReason.BUDGET)
        gold = request.gold
        question = (
            gold
            if isinstance(gold, Question)
            else Question(text=text, intent=Intent.DESCRIBE, ambiguities=("which?",))
        )
        return AgentRun(question, (), usage, StopReason.OUTPUT)


def _requests(*concept_ids: str) -> list[BankRequest]:
    return [r for r in bank_requests() if r.concept_id in concept_ids]


def _policy(
    price_per_job: float = 0.001, max_cost_usd: float = 10.0, model: str = "m"
) -> CostPolicy:
    return CostPolicy(
        model=model,
        price=lambda i, o: price_per_job,
        input_tokens_per_job=100,
        output_tokens_per_job=50,
        max_cost_usd=max_cost_usd,
    )


def test_runs_are_stored_and_resumed(tmp_path: Path) -> None:
    requests = _requests("R003")
    out = tmp_path / "runs.jsonl"
    agent = GoldAgent(requests)
    first = run_benchmark(
        requests,
        repetitions=1,
        agent=agent,
        budget=BUDGET,
        out_file=out,
        cost_policy=_policy(),
        log=lambda _: None,
    )
    assert first.ran == len(requests) and first.skipped_done == 0
    records = load_records(out)
    assert records[0]["parser_version"] == PARSER_VERSION and records[0]["model"] == "m"
    assert records[0]["question"]["intent"] == "compare"

    second = run_benchmark(
        requests,
        repetitions=1,
        agent=agent,
        budget=BUDGET,
        out_file=out,
        cost_policy=_policy(),
        log=lambda _: None,
    )
    assert second.skipped_done == len(requests) and second.ran == 0
    assert len(load_records(out)) == len(requests)


def test_an_estimate_over_the_cap_is_refused_before_any_run(tmp_path: Path) -> None:
    """`eval.paid_runs.run_paid_jobs` refuses the whole invocation up front rather than running
    part of it (refactor-paid-runs decision 7); the mid-run reservation and cap-trip themselves
    are covered by `tests/unit/eval/test_paid_runs.py`, against fake jobs."""
    requests = _requests("R003")
    out = tmp_path / "runs.jsonl"
    with pytest.raises(CostCapExceededError):
        run_benchmark(
            requests,
            repetitions=1,
            agent=GoldAgent(requests),
            budget=BUDGET,
            out_file=out,
            cost_policy=_policy(price_per_job=0.1, max_cost_usd=0.5),
            log=lambda _: None,
        )
    assert load_records(out) == []


def test_a_crash_is_logged_and_retried_next_time(tmp_path: Path) -> None:
    requests = _requests("R001")[:2]
    out = tmp_path / "runs.jsonl"
    logs: list[str] = []
    outcome = run_benchmark(
        requests,
        repetitions=1,
        agent=GoldAgent(requests, crash=frozenset({requests[0].id})),
        budget=BUDGET,
        out_file=out,
        cost_policy=_policy(),
        log=logs.append,
    )
    assert outcome.crashed == 1 and outcome.ran == 1
    assert any("CRASH" in line for line in logs)
    assert {r["request_id"] for r in load_records(out)} == {requests[1].id}


def test_a_failed_parse_records_why(tmp_path: Path) -> None:
    requests = _requests("R001")[:1]
    out = tmp_path / "runs.jsonl"
    run_benchmark(
        requests,
        repetitions=1,
        agent=GoldAgent(requests, fail=frozenset({requests[0].id})),
        budget=BUDGET,
        out_file=out,
        cost_policy=_policy(),
        log=lambda _: None,
    )
    (record,) = load_records(out)
    assert record["question"] is None and record["stop_reason"] == "budget"
    assert record["failure"] == "no submit_output call"


def test_the_report_scores_every_run_and_lists_failures(tmp_path: Path) -> None:
    requests = _requests("R003", "R005")
    broken = requests[1].id
    out = tmp_path / "runs.jsonl"
    for rep in (1, 2):
        run_benchmark(
            requests,
            repetitions=rep,
            agent=GoldAgent(requests, fail=frozenset({broken})),
            budget=BUDGET,
            out_file=out,
            cost_policy=_policy(),
            log=lambda _: None,
        )
    scored = score_records(load_records(out), bank_requests())
    summary = summarize_run(scored)
    assert summary["records"] == 2 * len(requests) and summary["repetitions"] == [1, 2]
    validity = summary["metrics"]["schema_validity"]
    assert (validity["hits"], validity["total"]) == (2 * len(requests) - 2, 2 * len(requests))
    assert summary["metrics"]["ambiguity_detection"]["value"] == 1.0
    assert summary["intent_agreement"]["total"] == len(requests)
    assert summary["intent_agreement"]["hits"] == len(requests) - 1
    assert set(summary["breakdowns"]["lang"]) >= {"en", "ca"}
    assert [failed_fields(s) for s in scored if s.request.id == broken][0][0] == "schema_validity"

    validity_ci = summary["intervals"]["schema_validity"]
    assert validity_ci["concepts"] == 2
    assert validity_ci["low"] <= validity["value"] <= validity_ci["high"]

    markdown = render_markdown("t", summary, scored)
    assert "| arm_structure |" in markdown and f"`{broken}` rep 1" in markdown
    assert "(2 concepts)" in markdown


def test_the_prompt_examples_share_nothing_with_the_bank() -> None:
    ids = set()
    for concept in CONCEPTS:
        ids |= set(re.findall(r"\b(?:[A-E][0-4]){1,2}\b|\bNEW\d\b|DEV-NET", concept.text))
    assert ids and not {i for i in ids if re.search(rf"\b{re.escape(i)}\b", SYSTEM_PROMPT)}


def test_the_cli_refuses_held_out_without_final_and_unapproved_models() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--name", "x", "--model", cli.APPROVED_MODELS[0], "--split", "held_out"])
    for picked in (["--concepts", "R003"], ["--requests", "R003.de"]):
        with pytest.raises(SystemExit):
            cli.main(["--name", "x", "--model", cli.APPROVED_MODELS[0], "--dry-run", *picked])
    with pytest.raises(SystemExit):
        cli.main(["--name", "x", "--model", "openai/gpt-5"])
    with pytest.raises(SystemExit):
        cli.main(["--name", "x"])


def test_the_dry_run_estimates_without_calling_a_model(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--name", "x", "--model", cli.APPROVED_MODELS[0], "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert f"{len(cli.select('dev'))} requests" in out and "estimated" in out
