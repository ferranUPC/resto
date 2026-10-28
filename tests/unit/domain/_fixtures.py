from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from resto.domain.entities.study import Study, StudyResolution, StudyStage
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.demand_spec import DemandProfile, DemandSpec
from resto.domain.value_objects.drafts import (
    DemandDraft,
    ExpertNoteDraft,
    NetworkDraft,
    ScenarioDraft,
)
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.fidelity import EdgeFidelity, Fidelity
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import GridNetwork, Polygon
from resto.domain.value_objects.phase import Phase
from resto.domain.value_objects.probe_report import ProbeReport
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.step_record import StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    FromStep,
    ObtainNetworkStep,
    PlanStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.traci_script import CloseLane, Rule, TraciScript, When

LANE = LaneTarget(edge_id="E12", lane_index=1)
NET = "abc123"  # the sample network's id (`_samples.network`)
DEMAND = "t1"  # the sample demand's id (`_samples.demand`)


def parsed_step(text: str) -> StepRecord:
    """The ok `parse` step of a study whose request was `text`."""
    return StepRecord("parse", StepStatus.OK, {"text": text}, usage=Usage(input_tokens=50))


def artifact(name: str, digest: str = "deadbeef", kind: str = "file") -> ArtifactRef:
    return ArtifactRef(path=Path(name), content_hash=digest, kind=kind)


def static_intervention() -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LANE,
        window=TimeWindow(7 * 3600, 10 * 3600),
    )


def dynamic_intervention() -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LANE,
        condition=Condition(metric=Metric.OCCUPANCY, target="E12", op=Operator.GT, value=0.8),
    )


def traci_script() -> TraciScript:
    """The script of `dynamic_intervention()`: close its lane when its condition holds."""
    return TraciScript(
        rules=(
            Rule(
                trigger=When(
                    Condition(metric=Metric.OCCUPANCY, target="E12", op=Operator.GT, value=0.8)
                ),
                action=CloseLane(edge_id="E12", lane_index=1),
            ),
        )
    )


def square_ring() -> tuple[tuple[float, float], ...]:
    """A closed (lat, lon) ring around a few blocks of the Eixample."""
    return ((41.38, 2.15), (41.38, 2.17), (41.40, 2.17), (41.40, 2.15), (41.38, 2.15))


def file_recipe() -> NetworkRecipe:
    """A recipe for a generated network: no OSM snapshot."""
    return NetworkRecipe(source=GridNetwork())


def area_recipe() -> NetworkRecipe:
    """A recipe for an area of interest: it carries the OSM snapshot it was built from."""
    return NetworkRecipe(
        source=Polygon(ring=square_ring(), osm_id=347950),
        osm_snapshot=artifact("eixample.osm", "snap1", "osm"),
    )


def good_sanity() -> SanityReport:
    return SanityReport(
        largest_scc_ratio=0.98,
        zero_length_edges=0,
        all_reachable_from_fringe=True,
        through_traffic_ratio=0.98,
    )


def bad_sanity() -> SanityReport:
    return SanityReport(
        largest_scc_ratio=0.80,
        zero_length_edges=3,
        all_reachable_from_fringe=False,
        through_traffic_ratio=0.80,
    )


def probe() -> ProbeReport:
    return ProbeReport(
        teleports=2,
        collisions=0,
        not_arrived=1,
        hot_edges=("E12",),
        evidence=artifact("edgedata.xml", "ed1", "edgedata"),
    )


def demand_spec() -> DemandSpec:
    return DemandSpec(
        profile=DemandProfile.PEAK, window=TimeWindow(7 * 3600, 10 * 3600), seed=1, scale=1.0
    )


def fidelity() -> Fidelity:
    return Fidelity(
        per_edge=(EdgeFidelity(edge_id="E12", target=1000.0, achieved=1050.0),),
        tolerance=0.15,
        evidence=artifact("calib-edgedata.xml", "ce1", "edgedata"),
    )


def network_draft(**overrides: object) -> NetworkDraft:
    kwargs: dict[str, object] = {
        "recipe": file_recipe(),
        "net_artifact": artifact("dev-net.net.xml", "abc123", "net"),
        "sanity_report": good_sanity(),
        "rationale": "kept the largest component and joined junctions",
    }
    kwargs.update(overrides)
    return NetworkDraft(**kwargs)  # type: ignore[arg-type]


def demand_draft(**overrides: object) -> DemandDraft:
    kwargs: dict[str, object] = {
        "spec": demand_spec(),
        "trips_artifact": artifact("trips.xml", "t1", "trips"),
        "routes_artifact": artifact("routes.xml", "r1", "routes"),
        "description": "Weekday morning commute fitted to the control-edge counts, 08:00–09:00.",
        "labels": frozenset({"counts", "weekday"}),
        "rationale": "sampled candidate routes against the control-edge counts",
    }
    kwargs.update(overrides)
    return DemandDraft(**kwargs)  # type: ignore[arg-type]


def scenario_draft(**overrides: object) -> ScenarioDraft:
    kwargs: dict[str, object] = {
        "interventions": (static_intervention(),),
        "mechanisms": (RegenerateDemandMechanism(demand_id="d2"),),
        "sumocfg": artifact("s1.sumocfg", "c1", "sumocfg"),
        "rationale": "a fixed window is served by a static rerouter",
    }
    kwargs.update(overrides)
    return ScenarioDraft(**kwargs)  # type: ignore[arg-type]


def expert_note_draft(**overrides: object) -> ExpertNoteDraft:
    kwargs: dict[str, object] = {
        "text": "E12 saturates in the last 20 minutes of the peak",
        "basis": Basis.OBSERVED,
        "evidence": (Evidence(kind=EvidenceKind.ARTIFACT, ref="edgedata.xml"),),
        "context_tags": frozenset({"peak"}),
    }
    kwargs.update(overrides)
    return ExpertNoteDraft(**kwargs)  # type: ignore[arg-type]


def build_step(
    arm: str = BASE_ARM,
    interventions: tuple[Intervention, ...] = (),
    network: str | FromStep = NET,
    demand: str | FromStep = DEMAND,
    depends_on: tuple[int, ...] = (),
    role: ExperimentRole = ExperimentRole.BASELINE,
) -> BuildScenarioStep:
    """A plan step building arm `arm` on the sample network and demand, unless told otherwise."""
    return BuildScenarioStep(
        network_id=network,
        demand_id=demand,
        arm=arm,
        role=role,
        purpose=f"arm {arm}",
        interventions=interventions,
        depends_on=depends_on,
    )


def run_step(step: int, seeds: tuple[int, ...] | None = None) -> RunSimulationStep:
    """A plan step running the scenario that step `step` builds."""
    return RunSimulationStep(scenario_id=FromStep(step), seeds=seeds, depends_on=(step,))


def study_plan(*steps: PlanStep, network: str | None = None) -> StudyPlan:
    """A plan made of exactly `steps`, as written, on the study network `network` (step 0, the
    `obtain_network` step, unless told otherwise)."""
    return StudyPlan(
        network_id=FromStep(0) if network is None else network,
        rationale="A plan by hand.",
        steps=steps,
    )


def _shifted(value: Any) -> Any:
    if isinstance(value, FromStep):
        return FromStep(value.step + 1)
    return value


def after_obtain_network(*steps: PlanStep) -> tuple[PlanStep, ...]:
    """`steps` behind the `obtain_network` step every plan has (ADR-0037 §2). The indexes a test
    writes (`FromStep`, `depends_on`) count from its first step, so they all move by one here."""
    moved: list[PlanStep] = []
    for step in steps:
        changes: dict[str, Any] = {
            f.name: _shifted(getattr(step, f.name))
            for f in dataclasses.fields(step)
            if isinstance(getattr(step, f.name), FromStep)
        }
        changes["depends_on"] = tuple(d + 1 for d in step.depends_on)
        moved.append(dataclasses.replace(step, **changes))  # type: ignore[type-var]
    return (ObtainNetworkStep(network_ref="RIVERSIDE"), *moved)


def plan_network(network: str | FromStep) -> str | FromStep:
    """The plan's `network_id` as `after_obtain_network` leaves the steps it indexes."""
    return _shifted(network)


ASKED = Question(text="what happens at peak?", intent=Intent.DESCRIBE)
PROPOSED = Question(text="close E12 at peak", intent=Intent.RUN)
ANSWER_EVIDENCE = (
    Evidence(kind=EvidenceKind.QUERY, ref="q1"),
    Evidence(kind=EvidenceKind.ARTIFACT, ref="/runs/r1/edgedata.xml"),
)


def study_with_rounds(
    rounds: int = 1,
    *,
    last_forced: bool = False,
    question: Question = ASKED,
    basis: Basis = Basis.OBSERVED,
    answer: ExpertAnswer | None = None,
    experiments: tuple[tuple[Experiment, ...], ...] = (),
    report: Report | None = None,
    study_id: str = "s",
) -> Study:
    """A study of `rounds` Expert rounds: every round but the last asks for a simulation, the last
    answers with `answer` (default: `basis` and `ANSWER_EVIDENCE`) and is forced by the limit when
    `last_forced`. `experiments` are those of each phase in order; with a `report` the study is
    completed, otherwise open at closing."""
    last = answer or ExpertAnswer(
        answer="E12",
        basis=basis,
        confidence=0.9,
        evidence=ANSWER_EVIDENCE,
        values=(Edges(edge_ids=("E12",), network_id=NET),),
    )
    ask = ExpertAnswer(
        answer="need a run",
        basis=Basis.EXTRAPOLATED,
        confidence=0.3,
        needs_simulation=True,
        proposed_experiment=PROPOSED,
    )
    plan = StudyPlan(network_id=FromStep(0), rationale="x", steps=(ObtainNetworkStep("RIVERSIDE"),))
    phases = tuple(
        Phase(
            question=question if k == 0 else PROPOSED,
            plan=plan,
            experiments=experiments[k] if k < len(experiments) else (),
            round=ExpertRound(
                "q",
                last if k == rounds - 1 else ask,
                forced_by_limit=last_forced and k == rounds - 1,
            ),
        )
        for k in range(rounds)
    )
    return Study(
        study_id=study_id,
        text=question.text,
        parse=parsed_step(question.text),
        stage=StudyStage.CLOSING,
        resolution=StudyResolution.COMPLETED if report else None,
        phases=phases,
        report=report,
        max_rounds=rounds if last_forced else max(rounds, 3),
    )
