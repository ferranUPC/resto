"""The probe's report where SUMO itself will not produce the case: a collision, which a probe on a
sane network does not provoke. The runner is replaced by one that writes the outputs by hand."""

from __future__ import annotations

from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.network_probe import SumoNetworkProber, _draw_trips
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.application.ports.sumo import RunOutput
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.kpis import Kpis
from tests.unit.application.tools._networks import grid_net

STATISTICS = """<statistics>
    <vehicles loaded="5" inserted="5" running="0" waiting="0"/>
    <teleports total="1" jam="1" yield="0" wrongLane="0"/>
    <safety collisions="2" emergencyStops="0" emergencyBraking="0"/>
    <vehicleTripStatistics count="4" duration="50" timeLoss="5"/>
</statistics>
"""
EDGEDATA = """<meandata>
    <interval begin="0" end="300">
        <edge id="A0A1" sampledSeconds="90" waitingTime="80"/>
        <edge id="A1A2" sampledSeconds="90" waitingTime="12"/>
    </interval>
    <interval begin="300" end="600">
        <edge id="A0A1" sampledSeconds="90" waitingTime="40"/>
    </interval>
</meandata>
"""


class HandWrittenRunner:
    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput:
        out_dir.mkdir(parents=True)
        (out_dir / "statistics.xml").write_text(STATISTICS)
        (out_dir / "edgedata.xml").write_text(EDGEDATA)
        return RunOutput(
            ok=True,
            error=None,
            artifacts=(
                artifact_ref(out_dir / "statistics.xml", "statistics"),
                artifact_ref(out_dir / "edgedata.xml", "edgedata"),
            ),
            wall_clock_s=0.0,
            kpis=Kpis(mean_delay=1.0, mean_travel_time=12.0, teleports=1, departed=5, arrived=4),
        )


def test_a_probe_report_carries_collisions_unarrived_vehicles_and_the_hot_edges(
    tmp_path: Path,
) -> None:
    net = artifact_ref(grid_net(tmp_path), "net")
    prober = SumoNetworkProber(HandWrittenRunner(), SumolibNetworkQuery)  # type: ignore[arg-type]

    report = prober.probe(net, seed=0, vehicles=5, duration_s=600.0, out_dir=tmp_path / "probe")

    assert report.collisions == 2
    assert report.teleports == 1
    assert report.not_arrived == 1
    assert report.hot_edges == ("A0A1",)  # 120 s of waiting; A1A2 stays under the threshold
    assert report.evidence.kind == "statistics"


class _TwoEdgeQuery:
    """Two passenger edges whose only path crosses an edge closed to passenger: the path exists
    for a router that ignores the vehicle class and not for one that honours it."""

    def edge_ids(self) -> list[str]:
        return ["a", "b"]

    def get_edge(self, edge_id: str) -> dict[str, object]:
        return {"allows": ["passenger"]}

    def shortest_path(self, from_edge: str, to_edge: str, vclass: str | None = None) -> list[str]:
        return [] if vclass == "passenger" else [from_edge, "service", to_edge]


def test_a_pair_whose_only_path_crosses_an_edge_closed_to_passenger_is_not_drawn() -> None:
    assert _draw_trips(_TwoEdgeQuery(), seed=0, vehicles=3, spread_s=100.0) == []  # type: ignore[arg-type]


class _PermissiveQuery(SumolibNetworkQuery):
    """A router that does not see the closed edge, as sumolib and SUMO may disagree (ticket 17)."""

    def shortest_path(self, from_edge: str, to_edge: str, vclass: str | None = None) -> list[str]:
        return super().shortest_path(from_edge, to_edge, None)  # type: ignore[return-value]


def test_a_trip_sumo_cannot_route_gives_a_report_instead_of_aborting(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    nodes = "".join(f'<node id="n{i}" x="{100.0 * i}" y="0"/>' for i in range(4))
    (plain / "n.nod.xml").write_text(f"<nodes>{nodes}</nodes>")
    (plain / "n.edg.xml").write_text(
        "<edges>"
        '<edge id="a" from="n0" to="n1"/>'
        '<edge id="service" from="n1" to="n2" disallow="passenger"/>'
        '<edge id="c" from="n2" to="n3"/>'
        "</edges>"
    )
    net = SubprocessNetconvertRunner().build(None, plain, [], tmp_path / "closed")
    prober = SumoNetworkProber(SubprocessSumoRunner(), _PermissiveQuery)

    report = prober.probe(net, seed=0, vehicles=2, duration_s=300.0, out_dir=tmp_path / "probe")

    # SUMO either drops the trip (not arrived) or lets it through and teleports it past the closed
    # edge; what matters is the report, and that both trips show up as trouble.
    assert report.not_arrived + report.teleports == 2
