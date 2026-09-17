"""Expert benchmark runner and report (E3.3), against the shared FakeToolAgent only."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from eval.expert_benchmark.bank import BenchmarkQuestion, Family
from eval.expert_benchmark.report import render_markdown, score_records, summarize
from eval.expert_benchmark.runner import Environment, load_records, run_benchmark

from resto.adapters.llm.agents.expert import EXPERT_VERSION
from resto.adapters.persistence.memory import InMemoryResultRepository, InMemoryScenarioRepository
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import AgentTask, Budget, Tool
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.application.tools.test_expert import DEV_NET

BUDGET = Budget(max_steps=6, max_tokens=2048, max_seconds=60.0)
QUESTIONS = [
    BenchmarkQuestion(
        id=f"S0{i}-desc-occ",
        family=Family.DESC_OCC,
        text=f"which edges exceed 3.5% occupancy? ({i})",
        network_id="n",
        result_ids=(),
        gold={"edges_above_threshold": ["B1B0"]},
    )
    for i in range(2)
]


def _answer(edge_ids: tuple[str, ...], ref: str = "q1", confidence: float = 0.9) -> ExpertAnswer:
    return ExpertAnswer(
        answer="B1B0 is above the threshold",
        basis=Basis.OBSERVED,
        confidence=confidence,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref=ref),),
        values=(Edges(edge_ids=edge_ids),),
    )


def _cite_one_call(task: AgentTask, tools: Sequence[Tool]) -> None:
    call_tool(tools, "get_edges", edge_ids=["B1B0"])


@pytest.fixture(scope="module")
def query() -> SumolibNetworkQuery:
    return SumolibNetworkQuery(DEV_NET)


def _run(agent: object, tmp_path: Path, query: SumolibNetworkQuery, **kwargs: object):  # noqa: ANN202
    options: dict[str, object] = {
        "repetitions": 1,
        "budget": BUDGET,
        "environment": lambda: Environment(
            InMemoryResultRepository(), InMemoryScenarioRepository(), query
        ),
        "out_file": tmp_path / "runs.jsonl",
        "model": "fake",
        "log": lambda _: None,
    }
    options.update(kwargs)
    return run_benchmark(QUESTIONS, agent=agent, **options)  # type: ignore[arg-type]


def test_every_question_and_repetition_is_stored_with_its_ledger(
    tmp_path: Path, query: SumolibNetworkQuery
) -> None:
    agent = FakeToolAgent(output=_answer(("B1B0",)), interact=_cite_one_call)
    outcome = _run(agent, tmp_path, query, repetitions=2, price=lambda i, o: 0.01)
    records = load_records(tmp_path / "runs.jsonl")
    assert outcome.ran == 4
    assert sorted((r["question_id"], r["repetition"]) for r in records) == [
        ("S00-desc-occ", 1), ("S00-desc-occ", 2), ("S01-desc-occ", 1), ("S01-desc-occ", 2)
    ]
    first = records[0]
    assert first["expert_version"] == EXPERT_VERSION
    assert first["steps"] == []  # the fake agent makes no model calls
    assert first["rejection"] is None
    assert first["ledger"][0]["tool"] == "get_edges"
    assert first["answer"]["values"][0]["edge_ids"] == ["B1B0"]
    assert outcome.cost_usd == pytest.approx(0.04)


def test_a_second_invocation_resumes_instead_of_paying_again(
    tmp_path: Path, query: SumolibNetworkQuery
) -> None:
    agent = FakeToolAgent(output=_answer(("B1B0",)), interact=_cite_one_call)
    _run(agent, tmp_path, query)
    outcome = _run(agent, tmp_path, query)
    assert (outcome.ran, outcome.skipped_done) == (0, 2)
    assert len(load_records(tmp_path / "runs.jsonl")) == 2


def test_the_cost_cap_stops_new_runs(tmp_path: Path, query: SumolibNetworkQuery) -> None:
    agent = FakeToolAgent(output=_answer(("B1B0",)), interact=_cite_one_call)
    outcome = _run(agent, tmp_path, query, price=lambda i, o: 1.0, max_cost_usd=1.0)
    assert (outcome.ran, outcome.skipped_budget) == (1, 1)


def test_crashes_are_not_stored_so_they_are_retried(
    tmp_path: Path, query: SumolibNetworkQuery
) -> None:
    def boom(task: AgentTask, tools: Sequence[Tool]) -> None:
        raise ConnectionError("openrouter down")

    outcome = _run(FakeToolAgent(output=None, interact=boom), tmp_path, query)
    assert (outcome.ran, outcome.crashed) == (0, 2)
    assert load_records(tmp_path / "runs.jsonl") == []


def test_promotion_rejections_are_stored_and_score_as_incorrect(
    tmp_path: Path, query: SumolibNetworkQuery
) -> None:
    agent = FakeToolAgent(output=_answer(("B1B0",), ref="q9"), interact=_cite_one_call)
    _run(agent, tmp_path, query)
    records = load_records(tmp_path / "runs.jsonl")
    assert "q9" in records[0]["rejection"]
    scored = score_records(records, QUESTIONS)
    assert not any(run.score.correct for run in scored)


def test_report_aggregates_repetitions_against_thresholds(
    tmp_path: Path, query: SumolibNetworkQuery
) -> None:
    right = FakeToolAgent(output=_answer(("B1B0",), confidence=1.0), interact=_cite_one_call)
    wrong = FakeToolAgent(output=_answer(("B2C2",), confidence=1.0), interact=_cite_one_call)
    _run(right, tmp_path, query, repetitions=1)
    _run(wrong, tmp_path, query, repetitions=2)  # only repetition 2 is new
    scored = score_records(load_records(tmp_path / "runs.jsonl"), QUESTIONS)
    summary = summarize(scored)

    assert summary["per_repetition"][1]["descriptive_accuracy"] == 1.0
    assert summary["per_repetition"][2]["descriptive_accuracy"] == 0.0
    assert summary["aggregate"]["descriptive_accuracy"]["mean"] == 0.5
    assert summary["aggregate"]["descriptive_accuracy"]["std"] == pytest.approx(0.7071, abs=1e-4)
    assert summary["aggregate"]["brier"]["mean"] == 0.5
    assert summary["aggregate"]["diag_accuracy"]["mean"] is None

    markdown = render_markdown("test", summary, scored)
    assert "| descriptive_accuracy | 0.50 | 0.71 | >= 0.90 ❌ |" in markdown
    assert "| S00-desc-occ | 2 | ❌ |" in markdown
    assert f"Expert: {EXPERT_VERSION}" in markdown
