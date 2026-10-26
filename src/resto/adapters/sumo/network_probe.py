"""`NetworkProber` over the shared `SumoRunner` (ADR-0045).

The demand is `vehicles` trips between random pairs of passenger edges that a route joins, drawn
from the seed and departing in the first third of the run, so the same seed gives the same demand.
SUMO routes each trip itself; a trip it cannot route is dropped (`ignore_route_errors`), not fatal,
so one bad pair never leaves the caller without a report. The run uses a short teleport time (`PROBE_TIME_TO_TELEPORT_S`), so a
vehicle stuck for two minutes counts: a probe is a smoke test, not a study scenario.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from random import Random

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.outputs import parse_edgedata
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.application.ports.network_query import EnumerableNetworkQuery
from resto.application.ports.sumo import SumoRunner
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.probe_report import ProbeReport

PROBE_TIME_TO_TELEPORT_S = 120.0
MAX_HOT_EDGES = 5
HOT_EDGE_WAIT_S = 60.0
_ATTEMPTS_PER_VEHICLE = 20


class SumoNetworkProber:
    def __init__(
        self,
        runner: SumoRunner,
        query_factory: Callable[[Path], EnumerableNetworkQuery] = SumolibNetworkQuery,
    ) -> None:
        self._runner = runner
        self._query_factory = query_factory

    def probe(
        self, net_xml: ArtifactRef, seed: int, vehicles: int, duration_s: float, out_dir: Path
    ) -> ProbeReport:
        out_dir.mkdir(parents=True, exist_ok=True)
        trips = _draw_trips(self._query_factory(net_xml.path), seed, vehicles, duration_s / 3)
        if not trips:
            raise ValueError("no routable pair of edges in this network: a probe has no demand")
        routes = out_dir / "probe.rou.xml"
        routes.write_text(_render_trips(trips), encoding="utf-8")
        cfg = SumocfgFileWriter().write(
            SimulationSettings(
                net_file=net_xml.path,
                route_files=(routes,),
                end=duration_s,
                time_to_teleport=PROBE_TIME_TO_TELEPORT_S,
                ignore_route_errors=True,
            ),
            out_dir,
            "probe.sumocfg",
        )
        run = self._runner.run_batch(cfg, seed, out_dir / "run")
        if not run.ok or run.kpis is None:
            raise RuntimeError(f"probe run failed: {run.error}")
        artifacts = {a.kind: a for a in run.artifacts}
        return ProbeReport(
            teleports=run.kpis.teleports,
            collisions=_collisions(artifacts["statistics"].path),
            not_arrived=len(trips) - run.kpis.arrived,
            hot_edges=_hot_edges(artifacts["edgedata"].path),
            evidence=artifacts["statistics"],
        )


def _draw_trips(
    query: EnumerableNetworkQuery, seed: int, vehicles: int, spread_s: float
) -> list[tuple[float, str, str]]:
    edges = [e for e in query.edge_ids() if "passenger" in query.get_edge(e)["allows"]]
    if len(edges) < 2:
        return []
    rng = Random(seed)
    trips: list[tuple[float, str, str]] = []
    for _ in range(vehicles * _ATTEMPTS_PER_VEHICLE):
        if len(trips) == vehicles:
            break
        origin, destination = rng.sample(edges, 2)
        if query.shortest_path(origin, destination, "passenger"):
            trips.append((round(rng.uniform(0.0, spread_s), 2), origin, destination))
    return sorted(trips)


def _render_trips(trips: list[tuple[float, str, str]]) -> str:
    root = ET.Element("routes")
    for number, (depart, origin, destination) in enumerate(trips):
        ET.SubElement(
            root,
            "trip",
            id=f"probe{number}",
            depart=str(depart),
            attrib={"from": origin, "to": destination},
        )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def _collisions(statistics_xml: Path) -> int:
    safety = ET.parse(statistics_xml).getroot().find("safety")
    return int(safety.get("collisions", "0")) if safety is not None else 0


def _hot_edges(edgedata_xml: Path) -> tuple[str, ...]:
    """The edges where vehicles waited most, worst first. Waiting a few seconds at a junction is
    normal, so an edge is hot only from `HOT_EDGE_WAIT_S` of waiting in total."""
    waited: dict[str, float] = defaultdict(float)
    for row in parse_edgedata(edgedata_xml):
        waited[row.edge_id] += row.waiting_time or 0.0
    hot = [e for e, wait in waited.items() if wait >= HOT_EDGE_WAIT_S]
    ranked = sorted(hot, key=lambda e: (-waited[e], e))
    return tuple(ranked[:MAX_HOT_EDGES])
