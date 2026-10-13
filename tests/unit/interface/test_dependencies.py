"""The composition root: `build_run_study` wires the real object graph, and one scripted study runs
through `RunStudy.execute` on a temporary SQLite database. Only the `ToolAgent` and the Network
Author (not implemented yet, E6.1) are fake; the network guard of `conftest.py` stays on."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.application.executor import StudySettings
from resto.application.ports.llm import AgentRun, AgentTask, Budget, StopReason, Tool
from resto.domain.entities.study import StudyResolution
from resto.domain.value_objects.answer_value import Measure, Quantity
from resto.domain.value_objects.drafts import (
    ClaimDraft,
    ExpertNoteDrafts,
    NetworkDraft,
    ReportDraft,
)
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.outcomes import Found, NetworkOutcome
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask
from resto.interface.dependencies import build_run_study
from tests.unit._paths import DEV_NET
from tests.unit.adapters.llm._fakes import call_tool
from tests.unit.domain._samples import network as sample_network

QUESTION = Question(
    text="how many lanes does the network have?",
    intent=Intent.DESCRIBE,
    network_ref="abc123",
    network_only=True,
)
ANSWER = ExpertAnswer(
    answer="the network was read",
    basis=Basis.OBSERVED,
    confidence=0.9,
    evidence=(Evidence(kind=EvidenceKind.QUERY, ref="q1"),),
    values=(Quantity(measure=Measure.MEAN_DELAY, value=24.4),),
)
REPORT = ReportDraft(
    summary="The network was read.",
    claims=(ClaimDraft(text="the network was read", evidence_refs=("q1",)),),
)


class ScriptedAgent:
    """A `ToolAgent` that answers by the output type asked for, like the real agents' ports."""

    def __init__(self) -> None:
        self.asked: list[type] = []

    def run(
        self, task: AgentTask, tools: Sequence[Tool], output: type, budget: Budget
    ) -> AgentRun[Any]:
        self.asked.append(output)
        if output is ExpertAnswer:
            call_tool(tools, "list_results", scenario_id="none")  # leaves q1 in the ledger
        scripted: dict[type, Any] = {
            Question: QUESTION,
            ExpertAnswer: ANSWER,
            ExpertNoteDrafts: ExpertNoteDrafts(),
            ReportDraft: REPORT,
        }
        return AgentRun(scripted[output], (), Usage(), StopReason.OUTPUT)


class NetworkAuthorStub:
    def obtain(self, task: ObtainNetworkTask) -> AgentRun[NetworkOutcome]:
        return AgentRun(Found(sample_network().network_id), (), Usage(), StopReason.OUTPUT)

    def author(self, task: NetworkTask) -> AgentRun[NetworkDraft]:
        raise NotImplementedError


class NullTracer:
    def emit(self, study_id: str, event: object) -> None:
        pass


def test_the_real_graph_runs_one_scripted_study(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "resto.sqlite")
    db.networks.store(
        replace(sample_network(), net_xml=replace(sample_network().net_xml, path=DEV_NET))
    )
    agent = ScriptedAgent()
    settings = StudySettings(out_dir=tmp_path, network_max_rounds=1, calibration_max_rounds=1)
    budget = Budget(max_steps=1, max_tokens=1, max_seconds=1.0)
    run_study = build_run_study(
        db=db, agent=agent, budget=budget, tracer=NullTracer(), settings=settings
    )
    # The Network Author is a placeholder until E6.1; the rest of the graph is the real one.
    deps = replace(
        run_study.deps, agents=replace(run_study.deps.agents, network_author=NetworkAuthorStub())
    )

    study = replace(run_study, deps=deps).execute("how many lanes does the network have?")

    db.close()
    assert study.resolution is StudyResolution.COMPLETED
    assert study.report is not None and study.report.summary == "The network was read."
    assert agent.asked[0] is Question and agent.asked[-1] is ReportDraft
