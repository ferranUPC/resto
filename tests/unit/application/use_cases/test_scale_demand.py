"""`scale_demand` (E2.3): deterministic regeneration of a `demand_scale`-derived `Demand`, no
agent involved — same "zero redundant work" shape as `run_simulation`, keyed on the derived
trips' own content hash."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from resto.adapters.persistence.memory import InMemoryDemandRepository
from resto.application.use_cases.scale_demand import scale_demand
from resto.domain.value_objects.artifact_ref import ArtifactRef
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network


class FakeScaler:
    def __init__(self, result: ArtifactRef) -> None:
        self.calls: list[tuple[ArtifactRef, float, Path]] = []
        self._result = result

    def scale(self, trips: ArtifactRef, factor: float, out_dir: Path) -> ArtifactRef:
        self.calls.append((trips, factor, out_dir))
        return self._result


class FakeDuarouter:
    def __init__(self, result: ArtifactRef) -> None:
        self.calls: list[tuple[ArtifactRef, ArtifactRef, int, Path]] = []
        self._result = result

    def duarouter(
        self, net_xml: ArtifactRef, trips: ArtifactRef, seed: int, out_dir: Path
    ) -> ArtifactRef:
        self.calls.append((net_xml, trips, seed, out_dir))
        return self._result

    def random_trips(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise AssertionError("not used")

    def route_sampler(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise AssertionError("not used")


def scaled_trips(digest: str = "scaled1") -> ArtifactRef:
    return ArtifactRef(path=Path("scaled.trips.xml"), content_hash=digest, kind="trips")


def routed(digest: str = "routed1") -> ArtifactRef:
    return ArtifactRef(path=Path("scaled.rou.xml"), content_hash=digest, kind="routes")


def test_scales_and_routes_a_new_demand(tmp_path: Path) -> None:
    demand = sample_demand()
    network = sample_network()
    scaler = FakeScaler(scaled_trips())
    duarouter = FakeDuarouter(routed())
    demands = InMemoryDemandRepository()

    derived = scale_demand(
        demand, network, 1.2, scaler=scaler, duarouter=duarouter, demands=demands, out_dir=tmp_path
    )

    assert derived.demand_id == "scaled1"
    assert derived.network_id == network.network_id
    assert derived.derived_from == demand.demand_id
    assert derived.spec.scale == pytest.approx(demand.spec.scale * 1.2)
    assert derived.trips == scaled_trips()
    assert derived.routes == routed()
    assert scaler.calls == [(demand.trips, 1.2, tmp_path)]
    assert duarouter.calls == [(network.net_xml, scaled_trips(), demand.spec.seed, tmp_path)]
    assert demands.get("scaled1") == derived


def test_an_existing_derived_demand_is_returned_without_calling_duarouter_again(
    tmp_path: Path,
) -> None:
    demand = sample_demand()
    network = sample_network()
    scaler = FakeScaler(scaled_trips())
    duarouter = FakeDuarouter(routed())
    demands = InMemoryDemandRepository()

    first = scale_demand(
        demand, network, 1.2, scaler=scaler, duarouter=duarouter, demands=demands, out_dir=tmp_path
    )
    second = scale_demand(
        demand, network, 1.2, scaler=scaler, duarouter=duarouter, demands=demands, out_dir=tmp_path
    )

    assert second == first
    assert len(duarouter.calls) == 1


def test_a_network_mismatch_is_rejected(tmp_path: Path) -> None:
    demand = replace(sample_demand(), network_id="other-network")
    network = sample_network()

    with pytest.raises(ValueError):
        scale_demand(
            demand,
            network,
            1.2,
            scaler=FakeScaler(scaled_trips()),
            duarouter=FakeDuarouter(routed()),
            demands=InMemoryDemandRepository(),
            out_dir=tmp_path,
        )
