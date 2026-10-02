"""`plan_problems` (study-flows.md §5): a plan checked against stored state and the phase's
question, without running a study. Each case asserts the exact problems found, in order."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace

import pytest

from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
)
from resto.application.executor.plan_validation import plan_problems
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.services.ids import result_id_for, scenario_id_for
from resto.domain.value_objects.arm import BASE_ARM, Arm
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    DeriveNetworkStep,
    FromStep,
    PlanStep,
    ReusedExperiment,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.domain._fixtures import (
    DEMAND,
    NET,
    after_obtain_network,
    artifact,
    build_step,
    plan_network,
    run_step,
    static_intervention,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network

CLOSURE = static_intervention()
KPIS = Kpis(mean_delay=24.4, mean_travel_time=85.4, teleports=0, departed=50, arrived=43)
NEW_EDGE = AddEdge("J7", "J9", lanes=2, speed=13.9, edge_id="J7J9")

DESCRIBE = Question(text="how congested is the peak?", intent=Intent.DESCRIBE)
WHAT_IF = Question(
    text="what if we close lane 1 of E12?", intent=Intent.COUNTERFACTUAL, interventions=(CLOSURE,)
)
PROPOSED = Question(text="close lane 1 of E12", intent=Intent.RUN, interventions=(CLOSURE,))
NEW_ROAD = Question(
    text="what does the J7-J9 edge do?",
    intent=Intent.RUN,
    arms=(Arm("edge", topology_changes=(NEW_EDGE,)),),
)


def plan(
    *steps: PlanStep, reused: tuple[ReusedExperiment, ...] = (), network: str | FromStep = NET
) -> StudyPlan:
    return StudyPlan(
        network_id=plan_network(network),
        rationale="as needed",
        steps=after_obtain_network(*steps),
        reused=reused,
    )


def reuse(scenario_id: str, arm: str = BASE_ARM) -> ReusedExperiment:
    return ReusedExperiment(scenario_id, arm, ExperimentRole.BASELINE, "already simulated")


class Stored:
    """The repositories a plan is checked against: the sample network and demand, and whatever
    scenarios and results a test stores."""

    def __init__(self) -> None:
        self.networks = InMemoryNetworkRepository()
        self.networks.store(sample_network())
        self.demands = InMemoryDemandRepository()
        self.demands.store(sample_demand())
        self.scenarios = InMemoryScenarioRepository()
        self.results = InMemoryResultRepository()

    def scenario(self, *, ok: bool = True) -> str:
        """A stored base scenario on the study network, with one result, ok or failed."""
        sid = scenario_id_for(NET, DEMAND, (), frozenset())
        self.scenarios.store(
            Scenario(
                scenario_id=sid,
                network_id=NET,
                demand_id=DEMAND,
                interventions=(),
                mechanisms=(),
                sumocfg=artifact("stored.sumocfg", "c0", "sumocfg"),
                content_hash="c0",
            )
        )
        self.results.store(
            SimulationResult(
                result_id=result_id_for(sid, 1, RunMode.BATCH.value),
                scenario_id=sid,
                seed=1,
                mode=RunMode.BATCH,
                status=RunStatus.OK if ok else RunStatus.FAILED,
                content_hash="h",
                kpis=KPIS if ok else None,
                error=None if ok else "Error: SUMO crashed",
            )
        )
        return sid

    def problems(
        self,
        plan: StudyPlan,
        question: Question = DESCRIBE,
        *,
        phase: int = 0,
        realised: Collection[str] = (),
        network_id: str | None = None,
    ) -> list[str]:
        return plan_problems(
            plan,
            question,
            phase=phase,
            realised=realised,
            network_id=network_id,
            networks=self.networks,
            demands=self.demands,
            scenarios=self.scenarios,
            results=self.results,
        )


@pytest.fixture
def stored() -> Stored:
    return Stored()


def test_a_valid_plan_has_no_problems(stored: Stored) -> None:
    assert stored.problems(plan(build_step(), run_step(0))) == []


@pytest.mark.parametrize(
    ("question", "bad_plan", "expected"),
    [
        (
            DESCRIBE,
            plan(build_step(), run_step(0), network="nope"),
            [
                "unknown network 'nope'",
                "step 1: its arm keeps the topology, but runs on another network",
            ],
        ),
        (
            DESCRIBE,
            plan(build_step(demand="nope"), run_step(0)),
            ["step 1: unknown demand 'nope'"],
        ),
        (DESCRIBE, plan(), ["arm 'base' is needed but not planned"]),
        (
            WHAT_IF,
            plan(build_step(), run_step(0), build_step("treatment", (CLOSURE,)), run_step(2)),
            ["arm 'treatment' is not needed by this phase"],
        ),
        (DESCRIBE, plan(build_step()), ["step 1: arm 'base' is built but never run"]),
        (
            DESCRIBE,
            plan(build_step(interventions=(CLOSURE,)), run_step(0)),
            ["step 1: its interventions are not those of its arm"],
        ),
    ],
    ids=[
        "unknown-network",
        "unknown-demand",
        "missing-arm",
        "extra-arm",
        "built-never-run",
        "wrong-interventions",
    ],
)
def test_an_invalid_plan_names_its_problem(
    stored: Stored, question: Question, bad_plan: StudyPlan, expected: list[str]
) -> None:
    assert stored.problems(bad_plan, question) == expected


def test_a_run_of_a_stored_scenario_id_is_rejected(stored: Stored) -> None:
    sid = stored.scenario()

    assert stored.problems(plan(RunSimulationStep(scenario_id=sid))) == [
        "step 1: run_simulation must run a scenario built by this plan "
        "(plan a build_scenario step: an existing scenario costs no agent call)",
        "arm 'base' is needed but not planned",
    ]


def test_an_arm_realised_in_an_earlier_phase_is_not_planned_again(stored: Stored) -> None:
    again = plan(build_step(), run_step(0), build_step("treatment", (CLOSURE,)), run_step(2))

    problems = stored.problems(again, PROPOSED, phase=1, realised={BASE_ARM}, network_id=NET)

    assert problems == ["arm 'base' was already realised in an earlier phase"]


def test_a_later_phase_plans_on_the_study_network(stored: Stored) -> None:
    other = artifact("other.net.xml", "other", "net")
    stored.networks.store(replace(sample_network(), network_id="other", net_xml=other))
    moved = plan(build_step("treatment", (CLOSURE,)), run_step(0))

    problems = stored.problems(moved, PROPOSED, phase=1, realised={BASE_ARM}, network_id="other")

    assert problems == [f"phase 1 plans on network {NET!r}, the study is about 'other'"]


def test_every_problem_in_one_plan_comes_back(stored: Stored) -> None:
    bad = plan(build_step(demand="nope", interventions=(CLOSURE,)), network="nope")

    assert stored.problems(bad) == [
        "unknown network 'nope'",
        "step 1: unknown demand 'nope'",
        "step 1: arm 'base' is built but never run",
        "step 1: its interventions are not those of its arm",
        "step 1: its arm keeps the topology, but runs on another network",
    ]


def test_a_reused_scenario_with_ok_results_realises_its_arm(stored: Stored) -> None:
    sid = stored.scenario()

    assert stored.problems(plan(reused=(reuse(sid),))) == []


def test_a_reused_scenario_without_ok_results_is_rejected(stored: Stored) -> None:
    sid = stored.scenario(ok=False)

    assert stored.problems(plan(reused=(reuse(sid),))) == [
        f"reused scenario {sid!r} has no ok results"
    ]


def test_a_reused_scenario_must_exist(stored: Stored) -> None:
    assert stored.problems(plan(reused=(reuse("nope"),))) == [
        "reused scenario 'nope' does not exist"
    ]


def test_a_topology_arm_on_the_study_network_is_rejected(stored: Stored) -> None:
    on_study_network = plan(build_step(), run_step(0), build_step("edge"), run_step(2))

    assert stored.problems(on_study_network, NEW_ROAD) == [
        "step 3: its arm changes the topology, but runs on the study network"
    ]


def test_a_topology_arm_runs_on_the_network_deriving_its_changes(stored: Stored) -> None:
    other_edge = AddEdge("J1", "J2", lanes=1, speed=13.9, edge_id="J1J2")
    derived = plan(
        DeriveNetworkStep(base_network_id=NET, modifications=(other_edge,)),
        build_step(),
        run_step(1),
        build_step("edge", network=FromStep(0), depends_on=(0,)),
        run_step(3),
    )

    assert stored.problems(derived, NEW_ROAD) == [
        "step 4: its network is derived with other changes than its arm's"
    ]
