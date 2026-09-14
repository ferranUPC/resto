from __future__ import annotations

from pathlib import Path

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.demand_spec import DemandProfile, DemandSpec
from resto.domain.value_objects.drafts import (
    DemandDraft,
    ExpertNoteDraft,
    NetworkDraft,
    ScenarioDraft,
)
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind
from resto.domain.value_objects.fidelity import EdgeFidelity, Fidelity
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.probe_report import ProbeReport
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.traci_script import DeclaredRule, TraciScript

LANE = LaneTarget(edge_id="E12", lane_index=1)


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


def runnable_script() -> TraciScript:
    return TraciScript(
        artifact=artifact("s1.py", "5c71p7", "script"),
        api_version="1",
        declared_rules=(
            DeclaredRule(trigger="when(occupancy(E12) > 0.8)", action="close_lane(E12_1)"),
        ),
        lint_ok=True,
        dry_run_ok=True,
    )


def file_recipe() -> NetworkRecipe:
    return NetworkRecipe(source=NetworkSource(kind="file", value="dev-net.osm"))


def good_sanity() -> SanityReport:
    return SanityReport(largest_scc_ratio=0.98, zero_length_edges=0, all_reachable_from_fringe=True)


def unlinted_script() -> TraciScript:
    return TraciScript(artifact=artifact("s2.py", "b4d", "script"), api_version="1")


def bad_sanity() -> SanityReport:
    return SanityReport(
        largest_scc_ratio=0.80, zero_length_edges=3, all_reachable_from_fringe=False
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
