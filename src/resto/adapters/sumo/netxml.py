"""NetworkQuery adapter over sumolib.

Wraps a single loaded `.net.xml`. Internal junction edges (`":A0_0"`-style) are never
parsed — `sumolib.net.readNet` excludes them unless asked for `withInternal=True`, which
matches what NetworkMCP callers (an LLM agent reasoning about topology) want: only the
"normal" edges of the network, never junction-internal geometry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import sumolib

# capacity_estimate() is a Greenshields estimate: q_max = v_free * k_jam / 4 (attained at
# v = v_free / 2). k_jam (jam density) is NOT an independently chosen constant - it is derived
# from SUMO's own default vehicle attributes below, and is only as correct as those defaults.
#
# CAUTION - precalculated, not queried: sumolib has no API to read these defaults back from the
# installed SUMO version, so they are hand-copied from SUMO's documented vType defaults for the
# pinned SUMO_VERSION (domain/constants.py). Re-derive _JAM_DENSITY_VEH_PER_KM by hand on any SUMO
# version bump, and treat capacity_estimate() as an order-of-magnitude figure only - it has no
# visibility into a scenario's actual Demand/vType (a Demand may not exist yet at query time; a
# vType may override length/minGap). Full rationale: docs/adr/0015 (capacity-estimate-greenshields).
_DEFAULT_VEHICLE_LENGTH_M = 5.0
_DEFAULT_MIN_GAP_M = 2.5
_JAM_DENSITY_VEH_PER_KM = 1000 / (_DEFAULT_VEHICLE_LENGTH_M + _DEFAULT_MIN_GAP_M)


class SumolibNetworkQuery:
    """`NetworkQuery` backed by `sumolib.net.Net` for one `.net.xml` file."""

    def __init__(self, net_xml_path: Path) -> None:
        self._net = sumolib.net.readNet(str(net_xml_path), withPrograms=True)

    def has_edge(self, edge_id: str) -> bool:
        return self._net.hasEdge(edge_id)

    def has_lane(self, edge_id: str, lane_index: int) -> bool:
        if not self._net.hasEdge(edge_id):
            return False
        return 0 <= lane_index < self._net.getEdge(edge_id).getLaneNumber()

    def has_tls(self, tls_id: str) -> bool:
        try:
            self._net.getTLS(tls_id)
        except KeyError:
            return False
        return True

    def get_edge(self, edge_id: str) -> Mapping[str, Any]:
        edge = self._net.getEdge(edge_id)  # raises KeyError on an unknown id
        return {
            "id": edge.getID(),
            "from_node": edge.getFromNode().getID(),
            "to_node": edge.getToNode().getID(),
            "length": edge.getLength(),
            "speed": edge.getSpeed(),
            "lane_count": edge.getLaneNumber(),
            "priority": edge.getPriority(),
            "type": edge.getType(),
            "allows": sorted(edge.getPermissions()),
            "shape": list(edge.getShape()),
        }

    def get_lanes(self, edge_id: str) -> Sequence[Mapping[str, Any]]:
        edge = self._net.getEdge(edge_id)  # raises KeyError on an unknown id
        return [
            {
                "id": lane.getID(),
                "index": lane.getIndex(),
                "length": lane.getLength(),
                "speed": lane.getSpeed(),
                "width": lane.getWidth(),
                "allows": sorted(lane.getPermissions()),
            }
            for lane in edge.getLanes()
        ]

    def get_neighbours(self, edge_id: str) -> Sequence[str]:
        """Downstream edges reachable in one hop (outgoing connections)."""
        edge = self._net.getEdge(edge_id)  # raises KeyError on an unknown id
        return sorted({out.getID() for out in edge.getOutgoing()})

    def shortest_path(self, from_edge: str, to_edge: str) -> Sequence[str]:
        from_e = self._net.getEdge(from_edge)  # raises KeyError on an unknown id
        to_e = self._net.getEdge(to_edge)  # raises KeyError on an unknown id
        edges, _cost = self._net.getShortestPath(from_e, to_e)
        if edges is None:
            return []
        return [e.getID() for e in edges]

    def edges_in_bbox(self, bbox: tuple[float, float, float, float]) -> Sequence[str]:
        """Edges whose bounding box overlaps `bbox = (xmin, ymin, xmax, ymax)` (net coords)."""
        xmin, ymin, xmax, ymax = bbox
        found = []
        for edge in self._net.getEdges():
            ex_min, ey_min, ex_max, ey_max = edge.getBoundingBox()
            if ex_min <= xmax and ex_max >= xmin and ey_min <= ymax and ey_max >= ymin:
                found.append(edge.getID())
        return sorted(found)

    def capacity_estimate(self, edge_id: str) -> float:
        """Greenshields max-flow estimate (veh/h) summed over the edge's lanes."""
        edge = self._net.getEdge(edge_id)  # raises KeyError on an unknown id
        free_flow_kmh = edge.getSpeed() * 3.6
        per_lane = free_flow_kmh * _JAM_DENSITY_VEH_PER_KM / 4
        return edge.getLaneNumber() * per_lane

    def get_tls(self, tls_id: str) -> Mapping[str, Any]:
        tls = self._net.getTLS(tls_id)  # raises KeyError on an unknown id
        return {
            "id": tls.getID(),
            "controlled_edges": sorted({e.getID() for e in tls.getEdges()}),
            "programs": {
                program_id: [(phase.state, phase.duration) for phase in program.getPhases()]
                for program_id, program in tls.getPrograms().items()
            },
        }
