from __future__ import annotations

from pathlib import Path

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import NetworkSource
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
