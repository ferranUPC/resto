"""`SumoDemandTools.duarouter` on DEV-NET with real SUMO (E2.3): what `scale_demand` calls to
route a resampled trips file. `random_trips`/`route_sampler` are work-plan E6.2/E6.5, still
`NotImplementedError`."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.demand import ROUTES_NAME, SumoDemandTools

DEV_NET_DIR = Path(__file__).resolve().parents[4] / "eval" / "dev-net"
NET = artifact_ref(DEV_NET_DIR / "dev-net.net.xml", "net")
TRIPS = artifact_ref(DEV_NET_DIR / "demand" / "low.trips.xml", "trips")


def test_duarouter_routes_the_trips_and_returns_the_output_ref(tmp_path: Path) -> None:
    result = SumoDemandTools().duarouter(NET, TRIPS, seed=1, out_dir=tmp_path)

    assert result.kind == "routes"
    assert result.path == (tmp_path / ROUTES_NAME).resolve()
    routes = ET.parse(result.path).getroot()
    vehicles = routes.findall("vehicle")
    assert len(vehicles) == len(ET.parse(TRIPS.path).getroot().findall("trip"))
    assert all(v.find("route") is not None for v in vehicles)


def test_duarouter_surfaces_its_own_error_message(tmp_path: Path) -> None:
    bad_trips_path = tmp_path / "bad.trips.xml"
    bad_trips_path.write_text(
        '<routes><trip id="x" depart="0" from="NOPE1" to="NOPE2"/></routes>', encoding="utf-8"
    )
    bad_trips = artifact_ref(bad_trips_path, "trips")

    with pytest.raises(RuntimeError, match="duarouter failed"):
        SumoDemandTools().duarouter(NET, bad_trips, seed=1, out_dir=tmp_path)


def test_random_trips_and_route_sampler_are_not_implemented_yet(tmp_path: Path) -> None:
    tools = SumoDemandTools()
    with pytest.raises(NotImplementedError):
        tools.random_trips(NET, 300.0, (0.0, 3600.0), seed=1, out_dir=tmp_path)
    with pytest.raises(NotImplementedError):
        tools.route_sampler(TRIPS, TRIPS, options=(), seed=1, out_dir=tmp_path)
