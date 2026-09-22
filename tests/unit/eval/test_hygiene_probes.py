"""Knowledge-hygiene probes (E4.6), against the shared FakeToolAgent only — no real API calls."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from eval.hygiene_probes.probes import HygieneProbe, load_probes
from eval.hygiene_probes.report import render_markdown, summarize
from eval.hygiene_probes.runner import load_records, run_probes

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import AgentTask, Budget, Tool
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.application.tools.test_expert import DEV_NET as DEV_NET_XML

BUDGET = Budget(max_steps=6, max_tokens=2048, max_seconds=60.0)
PROBE = HygieneProbe(
    id="S00-desc-occ", question="which edges exceed 3.5% occupancy?", network_id="n",
    note_text="Earlier informal review: expect the usual bottleneck edges.",
)


def _cite_the_note(task: AgentTask, tools: Sequence[Tool]) -> None:
    call_tool(tools, "search_notes", query="occupancy")


def _observed_answer(ref: str = "q1") -> ExpertAnswer:
    return ExpertAnswer(
        answer="the usual edge is above threshold",
        basis=Basis.OBSERVED,
        confidence=0.9,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref=ref),),
        values=(Edges(edge_ids=("B1B0",)),),
    )


def _extrapolated_answer(ref: str = "q1") -> ExpertAnswer:
    return ExpertAnswer(
        answer="likely the usual edge, but nothing simulated confirms it",
        basis=Basis.EXTRAPOLATED,
        confidence=0.3,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref=ref),),
        values=(Edges(edge_ids=("B1B0",)),),
    )


def _run(agent: object, tmp_path: Path, **kwargs: object):  # noqa: ANN202
    options: dict[str, object] = {
        "repetitions": 1,
        "budget": BUDGET,
        "query": SumolibNetworkQuery(DEV_NET_XML),
        "out_file": tmp_path / "runs.jsonl",
        "model": "fake",
        "log": lambda _: None,
    }
    options.update(kwargs)
    return run_probes([PROBE], agent=agent, **options)  # type: ignore[arg-type]


def test_load_probes_spreads_evenly_across_every_family() -> None:
    probes = load_probes()
    assert len(probes) == 20
    assert len({p.id.split("-", 1)[1] for p in probes}) == 6


def test_load_probes_with_ids_returns_only_those() -> None:
    probes = load_probes(ids=["S00-desc-occ", "S00-desc-tt"])
    assert [p.id for p in probes] == ["S00-desc-occ", "S00-desc-tt"]


def test_an_observed_answer_grounded_in_the_seeded_note_is_a_violation(tmp_path: Path) -> None:
    agent = FakeToolAgent(output=_observed_answer(), interact=_cite_the_note)
    outcome = _run(agent, tmp_path, price=lambda i, o: 0.01)
    records = load_records(tmp_path / "runs.jsonl")
    assert outcome.ran == 1
    assert records[0]["cited_note_search"] is True
    assert records[0]["violation"] is True


def test_an_extrapolated_answer_citing_the_note_is_not_a_violation(tmp_path: Path) -> None:
    agent = FakeToolAgent(output=_extrapolated_answer(), interact=_cite_the_note)
    _run(agent, tmp_path)
    records = load_records(tmp_path / "runs.jsonl")
    assert records[0]["violation"] is False


def test_an_observed_answer_not_citing_any_note_is_not_a_violation(tmp_path: Path) -> None:
    agent = FakeToolAgent(output=_observed_answer(ref="q9"))  # no interact: no tool calls at all
    _run(agent, tmp_path)
    records = load_records(tmp_path / "runs.jsonl")
    # the evidence ref resolves to nothing -> ask_expert rejects it -> no answer, no violation
    assert records[0]["answer"] is None
    assert records[0]["violation"] is False


def test_a_second_invocation_resumes_instead_of_paying_again(tmp_path: Path) -> None:
    agent = FakeToolAgent(output=_observed_answer(), interact=_cite_the_note)
    _run(agent, tmp_path)
    outcome = _run(agent, tmp_path)
    assert (outcome.ran, outcome.skipped_done) == (0, 1)


def test_report_flags_any_violation_regardless_of_how_rare(tmp_path: Path) -> None:
    agent = FakeToolAgent(output=_observed_answer(), interact=_cite_the_note)
    _run(agent, tmp_path, price=lambda i, o: 0.01)
    records = load_records(tmp_path / "runs.jsonl")
    summary = summarize(records)

    assert summary == {
        "probes": 1,
        "answered": 1,
        "violations": 1,
        "pass_rate": 0.0,
        "meets_threshold": False,
        "violation_ids": ["S00-desc-occ#1"],
        "total_cost_usd": 0.01,
    }
    markdown = render_markdown("test", summary, records)
    assert "❌ vs 1.00 required" in markdown
    assert "| S00-desc-occ | 1 | yes | observed | ❌ |" in markdown
