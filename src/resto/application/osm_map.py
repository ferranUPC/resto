"""An OpenStreetMap snapshot read as data, for the tools that look into it before and after
`netconvert` (ADR-0046): list its streets, select some of them into a derived snapshot, and say how
much of each street a built network kept and how far it ends from the places the user named.

A `.osm` file and a `.net.xml` are read with the stdlib XML parser, as `network_import` already
counts the edges of a `.net.xml`; no port stands in front of them.

- **A street** is the highways that share a `name` and a `ref`; highways with neither are grouped
  by their class (`primary_link`, `service`).
- **A selection** keeps the highways whose name contains one of the given names, or whose `ref`
  is one of the given refs, plus the connectors the caller asks for (`CONNECTORS`).
- **A piece** is a set of ways joined by shared nodes. Its ends are the two points farthest apart,
  found in two sweeps (exact on a corridor, close enough on anything else).
"""

from __future__ import annotations

import hashlib
import heapq
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args
from xml.etree import ElementTree

from resto.application.ports.osm import LocatedPlace
from resto.domain.services.geo import distance_m
from resto.domain.value_objects.artifact_ref import ArtifactRef

Point = tuple[float, float]  # (lat, lon)

Connectors = Literal["none", "links", "all"]
"""Which other ways a selection adds: none; the `*_link` ways that join two pieces of it; or any
road that joins two pieces of it (links, squares and crossings that carry another name)."""

CONNECTORS: tuple[str, ...] = get_args(Connectors)

MAX_CONNECTOR_M = 300.0
"""Longest chain of other ways a connector may be: a square or a large crossing, not a detour
through the next street."""

_NOT_ROADS = frozenset(
    {"footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "corridor", "track"}
    | {"platform", "proposed", "construction", "elevator"}
)
"""Highway classes that never join two carriageways for a car, so never a connector."""

MAX_LISTED = 40
"""Rows a listing returns at most, longest first; the rest are counted."""


@dataclass(frozen=True, slots=True)
class OsmWay:
    id: int
    nodes: tuple[int, ...]
    highway: str
    name: str
    ref: str

    @property
    def refs(self) -> frozenset[str]:
        """The `ref` tag holds several refs separated by ';' (e.g. 'N-340;B-23')."""
        return frozenset(r.strip().casefold() for r in self.ref.split(";") if r.strip())

    @property
    def street(self) -> tuple[str, str, str]:
        """The key of the street the way belongs to (see the module docstring)."""
        if self.name or self.ref:
            return (self.name, self.ref, "")
        return ("", "", self.highway)


@dataclass(frozen=True, slots=True)
class Piece:
    """Ways joined by shared nodes: how long they are and where they end."""

    ways: frozenset[int]
    length_m: float
    ends: tuple[Point, Point]

    def as_json(self) -> dict[str, Any]:
        return {"length_m": round(self.length_m), "ends": [_rounded(p) for p in self.ends]}


@dataclass(frozen=True, slots=True)
class NetEdge:
    """A normal edge of a built `.net.xml`, as the coverage report needs it: its junctions, its
    length and the OSM ways it was built from (`--output.original-names` writes them)."""

    id: str
    from_junction: str
    to_junction: str
    length_m: float
    osm_ways: frozenset[int]

    @staticmethod
    def read_all(net_xml: Path) -> tuple[NetEdge, ...]:
        edges = []
        for edge in ElementTree.parse(net_xml).getroot().iter("edge"):
            if edge.get("function") == "internal":
                continue
            lane = edge.find("lane")
            if lane is None:
                continue
            original = lane.find("param[@key='origId']")
            ids = original.get("value", "").split() if original is not None else []
            edges.append(
                NetEdge(
                    id=edge.get("id", ""),
                    from_junction=edge.get("from", ""),
                    to_junction=edge.get("to", ""),
                    length_m=float(lane.get("length", "0")),
                    osm_ways=frozenset(int(i) for i in ids if i.lstrip("-").isdigit()),
                )
            )
        return tuple(edges)


class OsmMap:
    """The nodes and highways of one `.osm` snapshot. Railways and other elements are kept only
    so the whole file can be filtered and written again."""

    def __init__(self, root: ElementTree.Element) -> None:
        self._root = root
        self.nodes: dict[int, Point] = {
            int(n.get("id", "0")): (float(n.get("lat", "0")), float(n.get("lon", "0")))
            for n in root.iter("node")
        }
        self.ways: dict[int, OsmWay] = {}
        for element in root.iter("way"):
            tags = {t.get("k", ""): t.get("v", "") for t in element.iter("tag")}
            if "highway" not in tags:
                continue
            way_id = int(element.get("id", "0"))
            self.ways[way_id] = OsmWay(
                id=way_id,
                nodes=tuple(int(nd.get("ref", "0")) for nd in element.iter("nd")),
                highway=tags["highway"],
                name=tags.get("name", ""),
                ref=tags.get("ref", ""),
            )

    @staticmethod
    def read(snapshot: Path) -> OsmMap:
        return OsmMap(ElementTree.parse(snapshot).getroot())

    def length_m(self, way: OsmWay) -> float:
        points = [self.nodes[n] for n in way.nodes if n in self.nodes]
        return sum(distance_m(a, b) for a, b in zip(points, points[1:], strict=False))

    # -- listing ----------------------------------------------------------------------------

    def streets(self, near: Point | None = None, radius_m: float = 0.0) -> list[dict[str, Any]]:
        """Every street with a node within `radius_m` of `near` (every street when `near` is
        None): name, ref, classes, total length and extent, longest first."""
        groups: dict[tuple[str, str, str], list[OsmWay]] = defaultdict(list)
        for way in self.ways.values():
            groups[way.street].append(way)
        rows = []
        for (name, ref, _), ways in groups.items():
            points = [self.nodes[n] for w in ways for n in w.nodes if n in self.nodes]
            if not points:
                continue
            if near is not None and min(distance_m(near, p) for p in points) > radius_m:
                continue
            rows.append(
                {
                    "name": name,
                    "ref": ref,
                    "classes": sorted({w.highway for w in ways}),
                    "length_m": round(sum(self.length_m(w) for w in ways)),
                    "extent": _extent(points),
                }
            )
        return sorted(rows, key=lambda r: (-r["length_m"], r["name"], r["ref"]))

    # -- selecting --------------------------------------------------------------------------

    def select(
        self, names: Sequence[str], refs: Sequence[str], connectors: Connectors
    ) -> tuple[OsmMap, dict[str, Any]]:
        """The snapshot with only the matching highways and the connectors asked for, and a
        summary of what was kept.

        Raises:
            ValueError: nothing to match, or nothing matches.
        """
        wanted_names = [n.strip().casefold() for n in names if n.strip()]
        wanted_refs = {r.strip().casefold() for r in refs if r.strip()}
        if not wanted_names and not wanted_refs:
            raise ValueError("give at least one name or ref to select")
        matched = {
            w.id
            for w in self.ways.values()
            if any(n in w.name.casefold() for n in wanted_names) or w.refs & wanted_refs
        }
        if not matched:
            raise ValueError(
                f"no highway in the snapshot has a name containing any of {list(names)} or a "
                f"ref in {list(refs)}: call list_streets to see the names and refs there are, "
                "or try another spelling"
            )
        joining = self._connectors(matched, connectors)
        kept = matched | joining
        pieces = self.pieces(kept)
        summary = {
            "streets": [
                {"name": name, "ref": ref, "length_m": round(length)}
                for (name, ref, _), length in self._lengths_by_street(matched).items()
            ],
            "connectors": [
                {
                    "name": name or None,
                    "ref": ref or None,
                    "class": cls or None,
                    "length_m": round(length),
                }
                for (name, ref, cls), length in self._lengths_by_street(joining).items()
            ][:MAX_LISTED],
            "pieces": len(pieces),
            "largest_pieces": [p.as_json() for p in pieces[:5]],
        }
        return self._only(kept), summary

    def _connectors(self, selected: set[int], connectors: Connectors) -> set[int]:
        """The other ways on a path shorter than `MAX_CONNECTOR_M` between two pieces of the
        selection: a multi-source shortest path from every selected node, labelled with its
        piece; an arc whose two ends were reached from different pieces closes such a path."""
        if connectors == "none":
            return set()
        piece_of = {
            n: i
            for i, p in enumerate(self.pieces(selected))
            for w in p.ways
            for n in self.ways[w].nodes
        }
        arcs: dict[int, list[tuple[int, float, int]]] = defaultdict(list)
        for way in self.ways.values():
            if way.id in selected or way.highway in _NOT_ROADS:
                continue
            if connectors == "links" and not way.highway.endswith("_link"):
                continue
            for a, b in zip(way.nodes, way.nodes[1:], strict=False):
                if a in self.nodes and b in self.nodes:
                    length = distance_m(self.nodes[a], self.nodes[b])
                    arcs[a].append((b, length, way.id))
                    arcs[b].append((a, length, way.id))
        distance: dict[int, float] = {n: 0.0 for n in piece_of if n in arcs}
        label = {n: piece_of[n] for n in distance}
        came_from: dict[int, tuple[int, int]] = {}
        queue = [(0.0, n) for n in sorted(distance)]
        while queue:
            reached, node = heapq.heappop(queue)
            if reached > distance[node]:
                continue
            for nxt, length, way_id in arcs[node]:
                total = reached + length
                if total <= MAX_CONNECTOR_M and total < distance.get(nxt, float("inf")):
                    distance[nxt], label[nxt], came_from[nxt] = total, label[node], (node, way_id)
                    heapq.heappush(queue, (total, nxt))
        found: set[int] = set()
        for a in sorted(arcs):
            for b, length, way_id in arcs[a]:
                if a not in label or b not in label or label[a] == label[b]:
                    continue
                if distance[a] + length + distance[b] <= MAX_CONNECTOR_M:
                    found.add(way_id)
                    for end in (a, b):
                        while end in came_from:
                            end, step = came_from[end]
                            found.add(step)
        return found

    def _lengths_by_street(self, way_ids: Iterable[int]) -> dict[tuple[str, str, str], float]:
        lengths: dict[tuple[str, str, str], float] = defaultdict(float)
        for way_id in way_ids:
            way = self.ways[way_id]
            lengths[way.street] += self.length_m(way)
        return dict(sorted(lengths.items(), key=lambda item: -item[1]))

    def _only(self, way_ids: set[int]) -> OsmMap:
        """A copy holding the ways `way_ids` and their nodes, in the original order, and the
        elements that are neither nodes, ways nor relations (bounds, notes)."""
        nodes = {n for w in way_ids for n in self.ways[w].nodes}
        root = ElementTree.Element(self._root.tag, self._root.attrib)
        for element in self._root:
            if element.tag == "node":
                keep = int(element.get("id", "0")) in nodes
            elif element.tag == "way":
                keep = int(element.get("id", "0")) in way_ids
            else:
                keep = element.tag != "relation"
            if keep:
                root.append(element)
        return OsmMap(root)

    def write(self, target: Path) -> ArtifactRef:
        """Writes the snapshot to `target` and returns it as an `osm` artifact. The same map
        always gives the same bytes, so the same selection gives the same `content_hash`."""
        body = ElementTree.tostring(self._root, encoding="UTF-8", xml_declaration=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".osm.part")
        partial.write_bytes(body)
        partial.replace(target)
        return ArtifactRef(target.resolve(), hashlib.sha256(body).hexdigest(), "osm")

    # -- pieces and coverage ----------------------------------------------------------------

    def pieces(self, way_ids: Iterable[int]) -> list[Piece]:
        """The ways grouped by shared nodes, longest piece first."""
        parent: dict[int, int] = {}

        def root(x: int) -> int:
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        ids = sorted(way_ids)
        for way_id in ids:
            first, *rest = self.ways[way_id].nodes
            for node in rest:
                parent[root(node)] = root(first)
        groups: dict[int, set[int]] = defaultdict(set)
        for way_id in ids:
            groups[root(self.ways[way_id].nodes[0])].add(way_id)
        pieces = [
            Piece(
                ways=frozenset(ways),
                length_m=sum(self.length_m(self.ways[w]) for w in ways),
                ends=_ends(
                    [
                        self.nodes[n]
                        for n in _sorted_nodes(self.ways[w] for w in ways)
                        if n in self.nodes
                    ]
                ),
            )
            for ways in groups.values()
        ]
        return sorted(pieces, key=lambda p: (-p.length_m, min(p.ways)))

    def coverage(self, edges: Sequence[NetEdge], places: Sequence[LocatedPlace]) -> dict[str, Any]:
        """What a network built from this snapshot covers: its extent, its connected
        components with their ends, the stretches of each street that did not make it into the
        network, and how far the network is from every place located in the run."""
        where = {j: p for j in _junctions(edges) if (p := self._junction_point(j)) is not None}
        components = _components(edges)
        rows: list[dict[str, Any]] = []
        ends: list[Point] = []
        for members in components[:5]:
            points = [where[j] for j in _junctions(members) if j in where]
            component_ends = _ends(points) if points else ()
            ends.extend(component_ends)
            rows.append(
                {
                    "edges": len(members),
                    "length_m": round(sum(e.length_m for e in members)),
                    "ends": [_rounded(p) for p in component_ends],
                }
            )
        return {
            "extent": _extent(list(where.values())) if where else None,
            "components": len(components),
            "largest_components": rows,
            "streets_with_missing_stretches": self._missing(edges),
            "places": [
                {
                    "query": place.query,
                    "point": _rounded((place.lat, place.lon)),
                    "to_network_m": _nearest((place.lat, place.lon), list(where.values())),
                    "to_nearest_end_m": _nearest((place.lat, place.lon), ends),
                }
                for place in places
            ],
        }

    def _junction_point(self, junction: str) -> Point | None:
        """A junction imported from OSM is named after its node; a joined one ('cluster_1_2')
        after several, and any of them will do."""
        for number in re.findall(r"\d+", junction):
            if int(number) in self.nodes:
                return self.nodes[int(number)]
        return None

    def _missing(self, edges: Sequence[NetEdge]) -> list[dict[str, Any]]:
        built = {w for e in edges for w in e.osm_ways}
        streets: dict[tuple[str, str, str], list[OsmWay]] = defaultdict(list)
        for way in self.ways.values():
            if way.name or way.ref:
                streets[way.street].append(way)
        rows = []
        for (name, ref, _), ways in streets.items():
            missing = [w.id for w in ways if w.id not in built]
            if not missing:
                continue
            total = sum(self.length_m(w) for w in ways)
            pieces = self.pieces(missing)
            lost = sum(p.length_m for p in pieces)
            row = {
                "name": name,
                "ref": ref,
                "in_snapshot_m": round(total),
                "in_network_m": round(total - lost),
                "missing": [p.as_json() for p in pieces[:3]],
            }
            rows.append((-lost, name, ref, row))
        return [row for *_, row in sorted(rows, key=lambda r: r[:3])[:10]]


def _sorted_nodes(ways: Iterable[OsmWay]) -> list[int]:
    return sorted({n for w in ways for n in w.nodes})


def _junctions(edges: Sequence[NetEdge]) -> list[str]:
    return sorted({e.from_junction for e in edges} | {e.to_junction for e in edges})


def _components(edges: Sequence[NetEdge]) -> list[list[NetEdge]]:
    """Edges grouped by shared junctions, ignoring direction, largest first."""
    parent: dict[str, str] = {}

    def root(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for edge in edges:
        parent[root(edge.to_junction)] = root(edge.from_junction)
    groups: dict[str, list[NetEdge]] = defaultdict(list)
    for edge in edges:
        groups[root(edge.from_junction)].append(edge)
    return sorted(groups.values(), key=lambda g: (-len(g), min(e.id for e in g)))


def _ends(points: Sequence[Point]) -> tuple[Point, Point]:
    """The two points farthest apart, by two sweeps from the first point."""
    first = max(points, key=lambda p: distance_m(points[0], p))
    second = max(points, key=lambda p: distance_m(first, p))
    return first, second


def _extent(points: Sequence[Point]) -> dict[str, float]:
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    return {
        "south": round(min(lats), 5),
        "west": round(min(lons), 5),
        "north": round(max(lats), 5),
        "east": round(max(lons), 5),
    }


def _nearest(point: Point, others: Sequence[Point]) -> int | None:
    return round(min(distance_m(point, p) for p in others)) if others else None


def _rounded(point: Point) -> list[float]:
    return [round(point[0], 5), round(point[1], 5)]
