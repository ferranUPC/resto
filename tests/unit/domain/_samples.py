"""One valid instance of every domain dataclass, for the round-trip suite of DoD §4.9.

`test_serialisation.py` asserts this mapping covers every dataclass under `resto.domain`, so a
new type cannot be added without also being round-tripped.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
from collections.abc import Callable

import resto.domain
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote, Provenance
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.services.note_ranking import ScoredNote
from resto.domain.value_objects.applied_action import ActionOrigin, AppliedAction
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.calibration_round import CalibrationRound
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.demand_source import (
    ExternalDatasetSource,
    HistoricalDbSource,
    ParametersSource,
)
from resto.domain.value_objects.demand_spec import DemandSpec
from resto.domain.value_objects.drafts import (
    DemandDraft,
    ExpertNoteDraft,
    NetworkDraft,
    RejectedIntervention,
    ScenarioDraft,
    UnresolvedIssue,
)
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_answer import (
    Basis,
    Evidence,
    EvidenceKind,
    ExpertAnswer,
)
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.fidelity import EdgeFidelity, Fidelity
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import (
    EdgeTarget,
    LaneTarget,
    TazTarget,
    TlsTarget,
)
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.mechanism import (
    RegenerateDemandMechanism,
    ScriptMechanism,
    StaticFileMechanism,
)
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.probe_report import ProbeReport
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.report import Claim, Report, ReportSection
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.step_record import StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_plan import PlanStep, StudyPlan
from resto.domain.value_objects.tasks import DemandTask, ExpertTask, NetworkTask, ScenarioTask
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
)
from resto.domain.value_objects.traci_script import DeclaredRule, TraciScript
from tests.unit.domain._fixtures import (
    artifact,
    demand_draft,
    demand_spec,
    dynamic_intervention,
    expert_note_draft,
    fidelity,
    file_recipe,
    good_sanity,
    network_draft,
    probe,
    runnable_script,
    scenario_draft,
    static_intervention,
)


def question() -> Question:
    return Question(
        text="what if we close lane 1 of E12 at peak?",
        intent=Intent.COUNTERFACTUAL,
        mode=Mode.FREE,
        network_ref="dev-net",
        interventions=(static_intervention(),),
        topology_changes=(AddEdge("J7", "J9", lanes=2, speed=13.9),),
        metrics_of_interest=("delay",),
        time_window=TimeWindow(7 * 3600, 10 * 3600),
        context_tags=frozenset({"peak"}),
    )


def expert_answer() -> ExpertAnswer:
    return ExpertAnswer(
        answer="delay rises by about 12 % on the corridor",
        basis=Basis.OBSERVED,
        confidence=0.8,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref="query_edgedata:r1", excerpt="E12 0.91"),),
    )


def study_plan() -> StudyPlan:
    return StudyPlan(
        steps=(
            PlanStep(module="build_scenario", inputs={"network_id": "n1"}),
            PlanStep(module="run_simulation", depends_on=(0,), expected_artifacts=("edgedata",)),
        ),
        rationale="baseline exists, only the treatment needs running",
        reuse_decisions=("reused network n1",),
    )


def report() -> Report:
    return Report(
        summary="closing the lane shifts delay to the parallel corridor",
        mode=Mode.FREE,
        basis=Basis.OBSERVED,
        sections=(ReportSection(title="Method", body="one baseline, one treatment"),),
        claims=(Claim(text="delay +12 %", evidence_refs=("r1",), value="12%"),),
        limitations=("single seed",),
    )


def network() -> Network:
    return Network(
        network_id="abc123",
        net_xml=artifact("dev-net.net.xml", "abc123", "net"),
        recipe=file_recipe(),
        sanity_report=good_sanity(),
        probe_report=probe(),
        label="dev-net",
    )


def demand() -> Demand:
    return Demand(
        demand_id="t1",
        network_id="abc123",
        spec=demand_spec(),
        trips=artifact("trips.xml", "t1", "trips"),
        routes=artifact("routes.xml", "r1", "routes"),
        sources=(ParametersSource(),),
        fidelity=fidelity(),
        calibration_rounds=(CalibrationRound(round=1, max_relative_error=0.05),),
    )


def scenario() -> Scenario:
    return Scenario(
        scenario_id="s1",
        network_id="abc123",
        demand_id="t1",
        interventions=(static_intervention(), dynamic_intervention()),
        mechanisms=(
            StaticFileMechanism(file_kind="rerouter", path=artifact("r.add.xml").path),
            ScriptMechanism(),
        ),
        sumocfg=artifact("s1.sumocfg", "c1", "sumocfg"),
        content_hash="c1",
        additional_files=(artifact("r.add.xml", "a1", "additional"),),
        context_tags=frozenset({"peak"}),
        traci_script=runnable_script(),
    )


def simulation_result() -> SimulationResult:
    return SimulationResult(
        result_id="res1",
        scenario_id="s1",
        seed=1,
        mode=RunMode.ONLINE,
        status=RunStatus.OK,
        content_hash="rc1",
        artifacts=(artifact("edgedata.xml", "ed1", "edgedata"),),
        kpis=Kpis(mean_delay=42.0, mean_travel_time=300.0, teleports=0, departed=500, arrived=498),
        applied_actions=(AppliedAction(step=120, action="close_lane", origin=ActionOrigin.RULE),),
        wall_clock_s=61.5,
    )


def expert_note() -> ExpertNote:
    return ExpertNote(
        note_id="n-1",
        network_id="abc123",
        study_id="st-1",
        text="E12 saturates in the last 20 minutes of the peak",
        provenance=Provenance.SIMULATION,
        basis=Basis.OBSERVED,
        scenario_id="s1",
        context_tags=frozenset({"peak"}),
    )


def study() -> Study:
    return Study(
        study_id="st-1",
        question=question(),
        status=StudyStatus.COMPLETED,
        plan=study_plan(),
        steps=(
            StepRecord(tool="run_simulation", status=StepStatus.OK, usage=Usage(simulations=1)),
        ),
        experiments=(
            Experiment(
                scenario_id="s1",
                role=ExperimentRole.TREATMENT,
                purpose="measure the closure",
                result_ids=("res1",),
            ),
        ),
        rounds=(
            ExpertRound(
                question="how bad is it?", answer=expert_answer(), triggered_experiments=(0,)
            ),
        ),
        report=report(),
        network_ids=("abc123",),
        note_ids=("n-1",),
    )


SAMPLES: dict[type, Callable[[], object]] = {
    # aggregates
    Network: network,
    Demand: demand,
    Scenario: scenario,
    SimulationResult: simulation_result,
    ExpertNote: expert_note,
    Study: study,
    # agent drafts
    NetworkDraft: network_draft,
    DemandDraft: demand_draft,
    ScenarioDraft: scenario_draft,
    ExpertNoteDraft: expert_note_draft,
    UnresolvedIssue: lambda: UnresolvedIssue(
        "junction", "J7", "turns point the wrong way", "set_connection"
    ),
    RejectedIntervention: lambda: RejectedIntervention(dynamic_intervention(), "unsupported in v1"),
    # study internals
    Question: question,
    StudyPlan: study_plan,
    PlanStep: lambda: PlanStep(module="ask_expert", inputs={"mode": "free"}),
    StepRecord: lambda: StepRecord(tool="ask_expert", status=StepStatus.OK),
    Usage: lambda: Usage(input_tokens=120, output_tokens=45, simulations=1),
    Experiment: lambda: Experiment(scenario_id="s1", role=ExperimentRole.BASELINE, purpose="ref"),
    ExpertRound: lambda: ExpertRound(question="why?", answer=expert_answer()),
    ExpertAnswer: expert_answer,
    Evidence: lambda: Evidence(kind=EvidenceKind.ARTIFACT, ref="edgedata.xml", excerpt="E12"),
    Report: report,
    ReportSection: lambda: ReportSection(title="Findings", body="delay rises"),
    Claim: lambda: Claim(text="delay +12 %", evidence_refs=("r1",), value="12%"),
    # network
    NetworkRecipe: file_recipe,
    NetworkSource: lambda: NetworkSource(kind="place", value="Barcelona, Eixample"),
    SanityReport: good_sanity,
    ProbeReport: probe,
    RemoveEdge: lambda: RemoveEdge(edge_id="E07"),
    AddEdge: lambda: AddEdge("J7", "J9", lanes=2, speed=13.9),
    SetLanes: lambda: SetLanes(edge_id="E12", lanes=3),
    SetSpeed: lambda: SetSpeed(edge_id="E12", speed=8.33),
    # demand
    DemandSpec: demand_spec,
    ParametersSource: ParametersSource,
    HistoricalDbSource: lambda: HistoricalDbSource(query={"day_type": "weekday", "hour": 8}),
    ExternalDatasetSource: lambda: ExternalDatasetSource(
        url="https://opendata.example/counts.csv",
        snapshot=artifact("counts.csv", "cs1", "dataset"),
        transformation="sum by hour",
    ),
    Fidelity: fidelity,
    EdgeFidelity: lambda: EdgeFidelity(edge_id="E12", target=1000.0, achieved=1050.0),
    CalibrationRound: lambda: CalibrationRound(
        round=1, max_relative_error=0.05, params={"scale": 1.1}
    ),
    # scenario
    Intervention: static_intervention,
    EdgeTarget: lambda: EdgeTarget(edge_id="E12"),
    LaneTarget: lambda: LaneTarget(edge_id="E12", lane_index=1),
    TlsTarget: lambda: TlsTarget(tls_id="J4"),
    TazTarget: lambda: TazTarget(taz_id="Z1"),
    TimeWindow: lambda: TimeWindow(7 * 3600, 10 * 3600),
    Condition: lambda: Condition(metric=Metric.OCCUPANCY, target="E12", op=Operator.GT, value=0.8),
    StaticFileMechanism: lambda: StaticFileMechanism(
        file_kind="vss", path=artifact("v.add.xml").path
    ),
    ScriptMechanism: ScriptMechanism,
    RegenerateDemandMechanism: lambda: RegenerateDemandMechanism(demand_id="d2"),
    TraciScript: runnable_script,
    DeclaredRule: lambda: DeclaredRule(trigger="at_time(3600)", action="close_lane(E12_1)"),
    # results
    Kpis: lambda: Kpis(
        mean_delay=42.0, mean_travel_time=300.0, teleports=1, departed=500, arrived=498
    ),
    AppliedAction: lambda: AppliedAction(
        step=120, action="set_speed", origin=ActionOrigin.CODE, params={"edge": "E12", "v": 8.33}
    ),
    ArtifactRef: lambda: artifact("edgedata.xml", "ed1", "edgedata"),
    # notes
    ScoredNote: lambda: ScoredNote(note=expert_note(), score=0.87),
    # tasks
    NetworkTask: lambda: NetworkTask(
        source=NetworkSource(kind="bbox", value="2.1,41.3,2.2,41.4"),
        goals=("drivable grid",),
        modifications=(RemoveEdge(edge_id="E07"),),
    ),
    DemandTask: lambda: DemandTask(
        network_id="abc123",
        profile=demand_spec().profile,
        seed=1,
        sources=(ParametersSource(),),
        control_edges=("E12",),
    ),
    ScenarioTask: lambda: ScenarioTask(
        network_id="abc123",
        demand_id="t1",
        interventions=(static_intervention(),),
        context_tags=frozenset({"peak"}),
    ),
    ExpertTask: lambda: ExpertTask(
        question="where does delay concentrate?",
        mode=Mode.FREE,
        network_id="abc123",
        result_ids=("res1",),
    ),
}


def domain_dataclasses() -> set[type]:
    """Every dataclass defined under `resto.domain`, found by walking the package."""
    found: set[type] = set()
    for module_info in pkgutil.walk_packages(resto.domain.__path__, "resto.domain."):
        module = importlib.import_module(module_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if dataclasses.is_dataclass(obj) and obj.__module__.startswith("resto.domain."):
                found.add(obj)
    return found
