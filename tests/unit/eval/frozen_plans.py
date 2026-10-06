"""The frozen oracle of the planner (refactor r13, ticket 03): plans written out by hand, as literal
expected values. No script writes this file and nothing here calls the plan bank or the planner, so
the planner is never its own oracle. Changing a plan here is an explicit edit, reviewed on its own.

Each plan is what a maintainer would plan for the bank question of the same concept id (the
question stays in `eval/request_bank/concepts.py`; the plan is not derived from it). Indexes in
`FromStep` and `depends_on` are written by hand. Every built arm is run once, after all the builds,
because the Executor's plan validation rejects a scenario that is built and never run (see
`test_frozen_plans.py`). `purpose` and `rationale` are prose and are not compared.

Phase 1 is a hand-written case that the bank does not exercise: the question has no `network_ref`
(the context's network id fills it) and an arm of an earlier phase is already realised.
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    RerouteDemandStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import AddEdge, RemoveEdge, SetLanes

BASELINE = ExperimentRole.BASELINE
TREATMENT = ExperimentRole.TREATMENT
COMPARISON = ExperimentRole.COMPARISON

_0800_0830 = TimeWindow(28800.0, 30600.0)
_0800_0900 = TimeWindow(28800.0, 32400.0)
_30_KMH = {"speed": 8.333}
_CROWDED = Condition(Metric.VEHICLE_COUNT, "B2C2", Operator.GT, 40)


def _obtain_network() -> ObtainNetworkStep:
    return ObtainNetworkStep(network_ref="DEV-NET")


def _obtain_demand(ref: str | None) -> ObtainDemandStep:
    return ObtainDemandStep(network_id=FromStep(0), seed=0, demand_ref=ref, depends_on=(0,))


def _derive(*changes: SetLanes | RemoveEdge | AddEdge) -> DeriveNetworkStep:
    return DeriveNetworkStep(base_network_id=FromStep(0), modifications=changes, depends_on=(0,))


def _reroute(derive_at: int) -> RerouteDemandStep:
    return RerouteDemandStep(
        demand_id=FromStep(1), network_id=FromStep(derive_at), depends_on=(1, derive_at)
    )


def _build(
    arm: str,
    role: ExperimentRole,
    network_at: int,
    demand_at: int,
    interventions: tuple[Intervention, ...] = (),
) -> BuildScenarioStep:
    return BuildScenarioStep(
        network_id=FromStep(network_at),
        demand_id=FromStep(demand_at),
        arm=arm,
        role=role,
        purpose=f"Arm {arm}",
        interventions=interventions,
        depends_on=(network_at, demand_at),
    )


def _run(build_at: int) -> RunSimulationStep:
    return RunSimulationStep(scenario_id=FromStep(build_at), depends_on=(build_at,))


def _plan(*steps: PlanStep) -> StudyPlan:
    return StudyPlan(network_id=FromStep(0), rationale="Frozen by hand.", steps=steps)


_LANE_1_CLOSED = Intervention(
    InterventionType.LANE_CLOSURE, LaneTarget("B0C0", 1), window=_0800_0830
)
_LANE_0_CLOSED = Intervention(
    InterventionType.LANE_CLOSURE, LaneTarget("B0C0", 0), window=_0800_0830
)
_C0D0_CLOSED = Intervention(InterventionType.EDGE_CLOSURE, EdgeTarget("C0D0"), window=_0800_0830)
_C2D2_CLOSED = Intervention(InterventionType.EDGE_CLOSURE, EdgeTarget("C2D2"), window=_0800_0830)
_B2C2_30_TIMED = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("B2C2"), params=_30_KMH, window=_0800_0830
)
_B2C2_30_HOUR = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("B2C2"), params=_30_KMH, window=_0800_0900
)
_B2C2_30_CROWDED = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("B2C2"), params=_30_KMH, condition=_CROWDED
)
_C2_PROGRAM_1_CROWDED = Intervention(
    InterventionType.SIGNAL_PROGRAM, TlsTarget("C2"), params={"program_id": "1"}, condition=_CROWDED
)
_C2_PROGRAM_1_HOUR = Intervention(
    InterventionType.SIGNAL_PROGRAM, TlsTarget("C2"), params={"program_id": "1"}, window=_0800_0900
)
_C3D3_LANE_2_CLOSED = Intervention(
    InterventionType.LANE_CLOSURE, LaneTarget("C3D3", 2), window=_0800_0830
)
_C3D3_30 = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("C3D3"), params=_30_KMH, window=_0800_0830
)
_NEW3_30_HOUR = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("NEW3"), params=_30_KMH, window=_0800_0900
)
_NEW3 = AddEdge("B1", "C2", lanes=2, speed=13.889, edge_id="NEW3")

FROZEN: dict[str, StudyPlan] = {
    # Network-only question: the plan is the obtain_network step and nothing else.
    "R074": _plan(_obtain_network()),
    # describe: the base arm only, as a baseline.
    "R002": _plan(
        _obtain_network(),
        _obtain_demand("peak"),
        _build("base", BASELINE, 0, 1),
        _run(2),
    ),
    # diagnose: the same shape as describe.
    "R008": _plan(
        _obtain_network(),
        _obtain_demand("peak"),
        _build("base", BASELINE, 0, 1),
        _run(2),
    ),
    # compare with one change: the base and one treatment.
    "R001": _plan(
        _obtain_network(),
        _obtain_demand("typical Monday morning traffic"),
        _build("base", BASELINE, 0, 1),
        _build("treatment", TREATMENT, 0, 1, (_LANE_1_CLOSED,)),
        _run(2),
        _run(3),
    ),
    # multi-arm, no contrast listed: each alternative against the base.
    "R003": _plan(
        _obtain_network(),
        _obtain_demand("peak"),
        _build("base", BASELINE, 0, 1),
        _build("closure", TREATMENT, 0, 1, (_C0D0_CLOSED,)),
        _build("speed_limit", TREATMENT, 0, 1, (_B2C2_30_TIMED,)),
        _run(2),
        _run(3),
        _run(4),
    ),
    # run with a topology change: derive, reroute, one treatment, no base.
    "R013": _plan(
        _obtain_network(),
        _obtain_demand(None),
        _derive(RemoveEdge("B1C1")),
        _reroute(2),
        _build("treatment", TREATMENT, 2, 3),
        _run(4),
    ),
    # compare with a new road: the base on the study network, the treatment on the derived one.
    "R014": _plan(
        _obtain_network(),
        _obtain_demand("low traffic"),
        _derive(AddEdge("B1", "C2", lanes=2, speed=13.889)),
        _reroute(2),
        _build("base", BASELINE, 0, 1),
        _build("treatment", TREATMENT, 2, 3),
        _run(4),
        _run(5),
    ),
    # conditional concept, run: the condition has no window and no base is planned.
    "R015": _plan(
        _obtain_network(),
        _obtain_demand("peak"),
        _build("treatment", TREATMENT, 0, 1, (_B2C2_30_CROWDED,)),
        _run(2),
    ),
    # two alternatives compared with each other only: no base, both comparisons.
    "R021": _plan(
        _obtain_network(),
        _obtain_demand(None),
        _build("lane_1", COMPARISON, 0, 1, (_LANE_1_CLOSED,)),
        _build("lane_0", COMPARISON, 0, 1, (_LANE_0_CLOSED,)),
        _run(2),
        _run(3),
    ),
    # a new edge, then the same edge plus a closure: one shared derived network.
    "R022": _plan(
        _obtain_network(),
        _obtain_demand("random traffic"),
        _derive(AddEdge("C1", "D2", lanes=1, speed=13.889)),
        _reroute(2),
        _build("base", BASELINE, 0, 1),
        _build("new_edge", TREATMENT, 2, 3),
        _build("new_edge_closure", TREATMENT, 2, 3, (_C2D2_CLOSED,)),
        _run(4),
        _run(5),
        _run(6),
    ),
    # two different topologies: one derive and one reroute each, the base on the study network.
    "R024": _plan(
        _obtain_network(),
        _obtain_demand("typical Monday morning traffic"),
        _derive(RemoveEdge("B0C0")),
        _reroute(2),
        _derive(SetLanes("B0C0", 1)),
        _reroute(4),
        _build("base", BASELINE, 0, 1),
        _build("removed", TREATMENT, 2, 3),
        _build("one_lane", TREATMENT, 4, 5),
        _run(6),
        _run(7),
        _run(8),
    ),
    # every arm changes the same topology and the contrasts are against "widened": no base.
    "R027": _plan(
        _obtain_network(),
        _obtain_demand("random traffic"),
        _derive(SetLanes("C3D3", 3)),
        _reroute(2),
        _build("widened", TREATMENT, 2, 3),
        _build("widened_closure", TREATMENT, 2, 3, (_C3D3_LANE_2_CLOSED,)),
        _build("widened_limit", TREATMENT, 2, 3, (_C3D3_30,)),
        _run(4),
        _run(5),
        _run(6),
    ),
    # conditional concept, multi-arm: the condition stays on the interventions of two arms.
    "R031": _plan(
        _obtain_network(),
        _obtain_demand("peak"),
        _build("base", BASELINE, 0, 1),
        _build("speed_limit", TREATMENT, 0, 1, (_B2C2_30_CROWDED,)),
        _build("signal", TREATMENT, 0, 1, (_C2_PROGRAM_1_CROWDED,)),
        _run(2),
        _run(3),
        _run(4),
    ),
    # the seven-arm concept: eight scenarios (base and seven arms) on four networks.
    "R065": _plan(
        _obtain_network(),
        _obtain_demand("peak"),
        _derive(SetLanes("C0D0", 3)),
        _reroute(2),
        _derive(RemoveEdge("B1C1")),
        _reroute(4),
        _derive(_NEW3),
        _reroute(6),
        _build("base", BASELINE, 0, 1),
        _build("a", COMPARISON, 0, 1, (_LANE_1_CLOSED,)),
        _build("b", COMPARISON, 0, 1, (_B2C2_30_HOUR,)),
        _build("widened_a", COMPARISON, 2, 3, (_LANE_1_CLOSED,)),
        _build("widened_c", COMPARISON, 2, 3, (_C2_PROGRAM_1_HOUR,)),
        _build("removed_b", TREATMENT, 4, 5, (_B2C2_30_HOUR,)),
        _build("new_edge", TREATMENT, 6, 7),
        _build("new_edge_d", TREATMENT, 6, 7, (_NEW3_30_HOUR,)),
        _run(8),
        _run(9),
        _run(10),
        _run(11),
        _run(12),
        _run(13),
        _run(14),
        _run(15),
    ),
}


@dataclass(frozen=True, slots=True)
class FrozenPhase1:
    """What the planner is given in phase 1 and the plan it must return. The context is plain
    fields so that this file does not depend on the type the planner will read it from."""

    question: Question
    network_id: str
    realised: tuple[str, ...]
    plan: StudyPlan


# An Expert proposed an experiment in round 1: no `network_ref` (the study's network fills it), a
# `run` of one treatment. The base arm was realised by phase 0 and is not planned again; the
# network and demand of the study are found, not rebuilt. The study's network is known by its id in
# phase 1, and `plan_problems` compares the plan's `network_id` and each arm's network with that id,
# so the plan and its build step name the id itself, not `FromStep(0)`. The id is the one of the
# sample network the validation test stores.
PHASE1 = FrozenPhase1(
    question=Question(
        text="Run the study network with a 30 km/h limit on B2C2 from 08:00 to 09:00.",
        intent=Intent.RUN,
        demand_ref="peak",
        interventions=(_B2C2_30_HOUR,),
    ),
    network_id="abc123",
    realised=("base",),
    plan=StudyPlan(
        network_id="abc123",
        rationale="Phase 1: run the proposed experiment on the study network.",
        steps=(
            ObtainNetworkStep(network_ref="abc123"),
            _obtain_demand("peak"),
            BuildScenarioStep(
                network_id="abc123",
                demand_id=FromStep(1),
                arm="treatment",
                role=TREATMENT,
                purpose="Arm treatment",
                interventions=(_B2C2_30_HOUR,),
                depends_on=(1,),
            ),
            _run(2),
        ),
    ),
)

SELECTED = tuple(FROZEN)
HARD = ("R065", "R024", "R022", "R027", "R031")
