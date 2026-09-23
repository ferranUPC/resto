"""Arms and contrasts: the combinations a question asks about (ADR-0027).

An arm is one combination of topology changes and interventions, simulated on the study's network
and demand. A contrast is one comparison between two arms. Only the arms some contrast needs are
simulated, never the cross product of every topology variant with every intervention set.
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    TopologyModification,
)

BASE_ARM = "base"
"""The implicit arm: the network and demand as they are, no changes, no interventions."""


@dataclass(frozen=True, slots=True)
class Arm:
    label: str
    topology_changes: tuple[TopologyModification, ...] = ()
    interventions: tuple[Intervention, ...] = ()

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("an Arm requires a label")
        if self.label == BASE_ARM:
            raise ValueError(f"'{BASE_ARM}' is the implicit arm and is never listed")
        if not self.topology_changes and not self.interventions:
            raise ValueError("an arm without changes or interventions is the base arm")
        added = [m.edge_id for m in self.topology_changes if isinstance(m, AddEdge) and m.edge_id]
        if len(set(added)) != len(added):
            raise ValueError("two added edges share an edge_id")
        self._check_targets()

    def _check_targets(self) -> None:
        """Interventions cannot act on what this arm's own changes remove."""
        removed = {m.edge_id for m in self.topology_changes if isinstance(m, RemoveEdge)}
        lanes = {m.edge_id: m.lanes for m in self.topology_changes if isinstance(m, SetLanes)}
        for intervention in self.interventions:
            target = intervention.target
            if not isinstance(target, EdgeTarget | LaneTarget):
                continue
            if target.edge_id in removed:
                raise ValueError(f"an intervention targets {target.edge_id}, removed by this arm")
            if isinstance(target, LaneTarget) and target.lane_index >= lanes.get(
                target.edge_id, target.lane_index + 1
            ):
                raise ValueError(
                    f"an intervention targets lane {target.lane_index} of {target.edge_id}, "
                    f"which this arm leaves with {lanes[target.edge_id]} lanes"
                )


@dataclass(frozen=True, slots=True)
class Contrast:
    """`treatment` measured against `reference`, both arm labels (`BASE_ARM` included)."""

    treatment: str
    reference: str = BASE_ARM

    def __post_init__(self) -> None:
        if not self.treatment.strip() or not self.reference.strip():
            raise ValueError("a Contrast names two arms")
        if self.treatment == self.reference:
            raise ValueError("a Contrast compares two different arms")
