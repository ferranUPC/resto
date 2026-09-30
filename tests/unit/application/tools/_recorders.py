"""Recording doubles for the Scenario Builder tools, shared by tool and agent tests."""

from __future__ import annotations

from pathlib import Path

from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism

LANE = LaneTarget(edge_id="A0A1", lane_index=0)


class RecordingDemandScaler:
    def __init__(self, result: ArtifactRef | None = None) -> None:
        self.calls: list[tuple[ArtifactRef, float, Path]] = []
        self._result = result or ArtifactRef(
            path=Path("scaled.trips.xml"), content_hash="scaled1", kind="trips"
        )

    def scale(self, trips: ArtifactRef, factor: float, out_dir: Path) -> ArtifactRef:
        self.calls.append((trips, factor, out_dir))
        return self._result


class RecordingDuarouter:
    def __init__(self, result: ArtifactRef | None = None) -> None:
        self.calls: list[tuple[ArtifactRef, ArtifactRef, int, Path]] = []
        self._result = result or ArtifactRef(
            path=Path("scaled.rou.xml"), content_hash="routed1", kind="routes"
        )

    def duarouter(
        self, net_xml: ArtifactRef, trips: ArtifactRef, seed: int, out_dir: Path
    ) -> ArtifactRef:
        self.calls.append((net_xml, trips, seed, out_dir))
        return self._result

    def random_trips(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise AssertionError("not used")

    def route_sampler(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise AssertionError("not used")


class RecordingDemandRepository:
    def __init__(self) -> None:
        self.stored: list = []  # noqa: ANN001

    def store(self, demand) -> None:  # noqa: ANN001
        self.stored.append(demand)

    def get(self, demand_id: str):  # noqa: ANN201
        return next((d for d in self.stored if d.demand_id == demand_id), None)

    def list(self, network_id: str):  # noqa: ANN201
        return [d for d in self.stored if d.network_id == network_id]


class RecordingWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[SimulationSettings, Path, str]] = []

    def write(self, settings: SimulationSettings, out_dir: Path, name: str) -> ArtifactRef:
        self.calls.append((settings, out_dir, name))
        return ArtifactRef(path=out_dir / name, content_hash="h", kind="sumocfg")


class RecordingAdditionalFileWriter:
    """Fake `AdditionalFileWriter`: records calls, returns a canned (mechanism, ArtifactRef)."""

    def __init__(self) -> None:
        self.calls: list[tuple[Intervention, Path]] = []

    def supports(self, intervention: Intervention) -> bool:
        return True

    def write(
        self, intervention: Intervention, out_dir: Path
    ) -> tuple[StaticFileMechanism, ArtifactRef]:
        self.calls.append((intervention, out_dir))
        path = (out_dir / "closure.add.xml").resolve()
        return StaticFileMechanism(file_kind="rerouter", path=path), ArtifactRef(
            path=path, content_hash="deadbeef", kind="additional"
        )
