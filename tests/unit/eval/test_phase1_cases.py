"""The phase-1 case set (r13 ticket 07): the 57 counterfactual questions of the Expert benchmark,
each as the experiment the Expert asks for once phase 0 realised the base arm. The planner and the
Executor (`run_study` on the fake world, with the real `plan_study`) must pass every case.
No database, no LLM, no network.

The expected plan is stated here from the stored question, never taken from the planner."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from eval.plan_bank.phase1 import Phase1Case, load_phase1

from resto.adapters.sumo.network_query_loader import StoredNetworkQueryLoader
from resto.application.ports.llm import AgentRun
from resto.domain.entities.study import StudyStatus
from resto.domain.services.planner import PlanningContext, plan_study
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism, StaticFileMechanism
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import StepStatus
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    RunSimulationStep,
)
from tests.unit.application._doubles import StubNetworkQuery
from tests.unit.application._world import World, abstains, answers, echo_draft, run_of
from tests.unit.domain._fixtures import NET, artifact

CASES = load_phase1()
IDS = sorted(CASES)


def test_the_set_is_the_57_counterfactual_questions_of_the_expert_benchmark() -> None:
    assert len(CASES) == 57
    assert all("-cf-" in cid for cid in CASES)
    assert {c.question.intent for c in CASES.values()} == {Intent.COMPARE}


@pytest.mark.parametrize("case_id", IDS)
def test_each_case_carries_what_phase_0_realised(case_id: str) -> None:
    case = CASES[case_id]

    assert case.context.phase == 1
    assert case.context.realised == (BASE_ARM,)
    assert case.context.network_id is not None
    assert case.question.network_ref is None
    assert len(case.baseline_result_ids) == 3  # the three default seeds of the base arm


@pytest.mark.parametrize("case_id", IDS)
def test_the_planner_plans_only_the_treatment_on_the_study_network(case_id: str) -> None:
    case = CASES[case_id]

    plan = plan_study(case.question, case.context)

    assert plan.network_id == case.context.network_id
    assert [type(s) for s in plan.steps] == [
        ObtainNetworkStep,
        ObtainDemandStep,
        BuildScenarioStep,
        RunSimulationStep,
    ]
    obtain, demand, build, run = plan.steps
    assert isinstance(obtain, ObtainNetworkStep)
    assert obtain.network_ref == case.context.network_id
    assert isinstance(demand, ObtainDemandStep)
    assert demand.demand_ref == case.question.demand_ref
    assert isinstance(build, BuildScenarioStep) and isinstance(run, RunSimulationStep)
    assert build.arm == "treatment" and build.role is ExperimentRole.TREATMENT
    assert build.network_id == case.context.network_id
    assert build.demand_id == FromStep(1)
    assert build.interventions == case.question.interventions
    assert len(build.interventions) == 1
    assert run.scenario_id == FromStep(2)
    assert plan.arms == ("treatment",)  # the base arm is not planned again


@pytest.mark.parametrize("case_id", IDS)
def test_a_proposal_that_names_the_study_network_plans_the_same(case_id: str) -> None:
    case = CASES[case_id]
    named = replace(case.question, network_ref=case.context.network_id)

    assert plan_study(named, case.context) == plan_study(case.question, case.context)


class _QueryOf(StubNetworkQuery):
    """The study network as far as the case's targets go: it has the edges, lanes and lights the
    experiment names, since the benchmark's own network is not stored in the fake world."""

    def __init__(self, case: Phase1Case) -> None:
        targets = [i.target for i in case.question.interventions]
        self._tls = {t.tls_id for t in targets if isinstance(t, TlsTarget)}
        super().__init__(
            edges={t.edge_id for t in targets if isinstance(t, EdgeTarget | LaneTarget)},
            lanes={(t.edge_id, t.lane_index) for t in targets if isinstance(t, LaneTarget)},
        )

    def has_tls(self, tls_id: str) -> bool:
        return tls_id in self._tls


def _builder(task: Any) -> AgentRun[ScenarioDraft]:
    """A Builder that implements what it was asked: a demand regenerated for `demand_scale`, a
    static file for the other types (as `echo_draft` does)."""
    mechanisms = tuple(
        RegenerateDemandMechanism(demand_id=task.demand_id)
        if i.type is InterventionType.DEMAND_SCALE
        else StaticFileMechanism(file_kind="rerouter", path=Path(f"{n}.add.xml"))
        for n, i in enumerate(task.interventions)
    )
    draft = ScenarioDraft(
        interventions=task.interventions,
        mechanisms=mechanisms,
        sumocfg=artifact("s.sumocfg", "c1", "sumocfg"),
        rationale="implemented as asked",
    )
    return run_of(draft, tokens=100)


def _executor_case(tmp_path: Path, case: Phase1Case) -> World:
    """Phase 0 describes the study's network (base arm); the Expert then asks for the case's
    experiment, which the real planner plans in phase 1. Only the agents are fake."""
    described = Question(text="how congested is the peak?", intent=Intent.DESCRIBE, network_ref=NET)
    world = World(
        tmp_path,
        question=described,
        expert=(abstains(case.question), answers()),
        builder=(echo_draft, _builder),
    )
    query = _QueryOf(case)
    loader = StoredNetworkQueryLoader(world.networks, lambda _path: query)
    world.deps = replace(world.deps, planner=plan_study, network_query_loader=loader)
    return world


@pytest.mark.parametrize("case_id", IDS)
def test_the_executor_runs_each_case_through_both_phases(tmp_path: Path, case_id: str) -> None:
    case = CASES[case_id]
    world = _executor_case(tmp_path, case)

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert [e.arm for p in study.phases for e in p.experiments] == [BASE_ARM, "treatment"]
    assert study.phases[1].question == case.question
    assert [s.status for s in study.phases[1].steps] == [StepStatus.OK] * len(study.phases[1].steps)
    (task,) = [call[0] for call in world.builder.calls[1:]]
    assert task.interventions == case.question.interventions
    assert len(world.runner.calls) == 8  # per arm: the load check and three seeds, once each


def test_the_planning_context_of_the_study_matches_the_case_context(tmp_path: Path) -> None:
    case = CASES[IDS[0]]
    seen: list[PlanningContext] = []

    def spy(question: Question, context: PlanningContext):  # type: ignore[no-untyped-def]
        seen.append(context)
        return plan_study(question, context)

    world = _executor_case(tmp_path, case)
    world.deps = replace(world.deps, planner=spy)
    world.run()

    assert seen[1] == replace(case.context, network_id=NET)
