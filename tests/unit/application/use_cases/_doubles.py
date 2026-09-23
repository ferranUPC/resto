"""Test doubles shared by the use-case tests: a `NetworkQuery` answering only existence checks and
a scripted `SumoRunner`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Any

from resto.application.ports.sumo import RunOutput
from resto.domain.value_objects.artifact_ref import ArtifactRef


class StubNetworkQuery:
    def __init__(
        self,
        edges: AbstractSet[str] = frozenset(),
        lanes: AbstractSet[tuple[str, int]] = frozenset(),
    ) -> None:
        self._edges = edges
        self._lanes = lanes

    def has_edge(self, edge_id: str) -> bool:
        return edge_id in self._edges

    def has_lane(self, edge_id: str, lane_index: int) -> bool:
        return (edge_id, lane_index) in self._lanes

    def has_tls(self, tls_id: str) -> bool:
        raise AssertionError("not used by this intervention")

    def get_edge(self, edge_id: str) -> Mapping[str, Any]:
        raise AssertionError("not used")

    def get_lanes(self, edge_id: str) -> Sequence[Mapping[str, Any]]:
        raise AssertionError("not used")

    def get_neighbours(self, edge_id: str) -> Sequence[str]:
        raise AssertionError("not used")

    def shortest_path(self, from_edge: str, to_edge: str) -> Sequence[str]:
        raise AssertionError("not used")

    def edges_in_bbox(self, bbox: tuple[float, float, float, float]) -> Sequence[str]:
        raise AssertionError("not used")

    def capacity_estimate(self, edge_id: str) -> float:
        raise AssertionError("not used")

    def get_tls(self, tls_id: str) -> Mapping[str, Any]:
        raise AssertionError("not used")


class FakeRunner:
    """Returns `outputs` in order, then `default` for every further run (an empty queue with no
    default is a test error)."""

    def __init__(self, outputs: list[RunOutput], default: RunOutput | None = None) -> None:
        self._outputs = outputs
        self._default = default
        self.calls: list[tuple[ArtifactRef, int, Path]] = []

    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput:
        self.calls.append((sumocfg, seed, out_dir))
        if not self._outputs and self._default is not None:
            return self._default
        return self._outputs.pop(0)

    def run_online(
        self, sumocfg: ArtifactRef, script: ArtifactRef, seed: int, out_dir: Path
    ) -> RunOutput:
        raise AssertionError("not used")
