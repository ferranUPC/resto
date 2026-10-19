"""An OpenStreetMap snapshot read as data, for the tools that look into it before and after
`netconvert` (ADR-0046). `OsmMap` lists the streets of a snapshot and selects some of them into a
derived snapshot; `OsmMap.coverage` compares a built network with the snapshot it came from.

A `.osm` file and a `.net.xml` are read with the stdlib XML parser, as `network_import` already
counts the edges of a `.net.xml`; no port stands in front of them.

- **A street** is the highways that share a `name` and a `ref`; highways with neither are grouped
  by their class (`primary_link`, `service`).
- **A selection** keeps the roads whose name contains one of the given names, or whose `ref` is
  one of the given refs, plus the connectors the caller asks for (`Connectors`). Footways, paths,
  cycleways and the like are never selected, whatever their name, and nothing but highways is
  kept: the rail profile finds no railway in a selection.
- **A piece** is a set of ways joined by shared nodes, whatever their direction. Its ends are the
  two points farthest apart, found in two sweeps (exact on a corridor, close enough on anything
  else).
"""

from __future__ import annotations

import copy
import hashlib
import heapq
import re
from collections import defaultdict
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar
from xml.etree import ElementTree

from resto.application.ports.osm import LocatedPlace
from resto.domain.services.geo import distance_m
from resto.domain.value_objects.artifact_ref import ArtifactRef

Point = tuple[float, float]  # (lat, lon)
StreetKey = tuple[str, str, str]  # (name, ref, class); the class only when name and ref are empty

Connectors = Literal["none", "links", "all"]
"""Which other ways a selection adds: none; the `*_link` ways that join two pieces of it; or any
road that joins two pieces of it (links, squares and crossings that carry another name)."""

MAX_CONNECTOR_M = 300.0
"""Longest path of other ways a connector may be: a square or a large crossing, not a detour
through the next street."""

_NOT_ROADS = frozenset(
    {"footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "corridor", "track"}
    | {"platform", "proposed", "construction", "elevator"}
)
"""Highway classes a car never drives on: never selected and never a connector."""

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
    def street(self) -> StreetKey:
        """The key of the street the way belongs to (see the module docstring)."""
        if self.name or self.ref:
            return (self.name, self.ref, "")
        return ("", "", self.highway)

    @property
    def is_road(self) -> bool:
        return self.highway not in _NOT_ROADS


@dataclass(frozen=True, slots=True)
class Piece:
    """Ways joined by shared nodes: how long they are and where they end."""

    ways: frozenset[int]
    length_m: float
    ends: tuple[Point, Point]

    def as_json(self) -> dict[str, Any]:
        return {"length_m": round(self.length_m), "ends": [_rounded(p) for p in self.ends]}


K = TypeVar("K", bound=Hashable)


class _Joined(Generic[K]):
    """Which keys end up joined (union-find with path halving)."""

    def __init__(self) -> None:
        self._parent: dict[K, K] = {}

    def root(self, key: K) -> K:
        while self._parent.setdefault(key, key) != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def join(self, a: K, b: K) -> None:
        self._parent[self.root(b)] = self.root(a)


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

    @staticmethod
    def junctions(edges: Iterable[NetEdge]) -> list[str]:
        return sorted({j for e in edges for j in (e.from_junction, e.to_junction)})

    @staticmethod
    def components(edges: Sequence[NetEdge]) -> list[list[NetEdge]]:
        """Edges grouped by shared junctions, whatever their direction, largest first."""
        joined: _Joined[str] = _Joined()
        for edge in edges:
            joined.join(edge.from_junction, edge.to_junction)
        groups: dict[str, list[NetEdge]] = defaultdict(list)
        for edge in edges:
            groups[joined.root(edge.from_junction)].append(edge)
        return sorted(groups.values(), key=lambda g: (-len(g), min(e.id for e in g)))


class OsmMap:
    """The nodes and highways of one `.osm` snapshot. The parsed file is kept whole, so a
    selection can be written again with the same elements in the same order."""

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
        points = self._points([way])
        return sum(distance_m(a, b) for a, b in zip(points, points[1:], strict=False))

    def _points(self, ways: Iterable[OsmWay]) -> list[Point]:
        return [self.nodes[n] for w in ways for n in w.nodes if n in self.nodes]

    def _by_street(self, ways: Iterable[OsmWay]) -> dict[StreetKey, list[OsmWay]]:
        streets: dict[StreetKey, list[OsmWay]] = defaultdict(list)
        for way in ways:
            streets[way.street].append(way)
        return streets

    # -- listing ----------------------------------------------------------------------------

    def streets(self, near: Point | None = None, radius_m: float = 0.0) -> list[dict[str, Any]]:
        """Every street with a node within `radius_m` of `near` (every street when `near` is
        None): name, ref, classes, total length and extent, longest first."""
        rows = []
        for (name, ref, _), ways in self._by_street(self.ways.values()).items():
            points = self._points(ways)
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
        """The snapshot with only the matching roads and the connectors asked for, and a summary
        of what was kept.

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
            if w.is_road
            and (any(n in w.name.casefold() for n in wanted_names) or w.refs & wanted_refs)
        }
        if not matched:
            raise ValueError(
                f"no road in the snapshot has a name containing any of {list(names)} or a "
                f"ref in {list(refs)}: call list_streets to see the names and refs there are, "
                "or try another spelling"
            )
        spans = self._connectors(matched, connectors)
        selected = self._only(matched, spans)
        joining = [selected.ways[w] for w in sorted(spans)]
        pieces = selected.pieces(selected.ways)
        summary = {
            "streets": [
                {"name": name, "ref": ref, "length_m": round(length)}
                for (name, ref, _), length in selected._lengths([selected.ways[w] for w in matched])
            ],
            "connectors": [
                {
                    "name": name or None,
                    "ref": ref or None,
                    "class": cls or None,
                    "length_m": round(length),
                }
                for (name, ref, cls), length in selected._lengths(joining)
            ][:MAX_LISTED],
            "pieces": len(pieces),
            "largest_pieces": [p.as_json() for p in pieces[:5]],
        }
        return selected, summary

    def _connectors(self, selected: set[int], connectors: Connectors) -> dict[int, set[int]]:
        """The other roads on a path of at most `MAX_CONNECTOR_M` between two pieces of the
        selection, each with the nodes of it the path uses: a shortest path from every selected
        node at once, labelled with its piece; an arc whose two ends were reached from different
        pieces closes such a path."""
        if connectors == "none":
            return {}
        piece_of = {
            n: i
            for i, p in enumerate(self.pieces(selected))
            for w in p.ways
            for n in self.ways[w].nodes
        }
        arcs: dict[int, list[tuple[int, float, int]]] = defaultdict(list)
        for way in self.ways.values():
            if way.id in selected or not way.is_road:
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
        spans: dict[int, set[int]] = defaultdict(set)
        for a in sorted(arcs):
            for b, length, way_id in arcs[a]:
                if a not in label or b not in label or label[a] == label[b]:
                    continue
                if distance[a] + length + distance[b] <= MAX_CONNECTOR_M:
                    spans[way_id] |= {a, b}
                    for end in (a, b):
                        while end in came_from:
                            previous, step = came_from[end]
                            spans[step] |= {previous, end}
                            end = previous
        return dict(spans)

    def _lengths(self, ways: Iterable[OsmWay]) -> list[tuple[StreetKey, float]]:
        """Total length per street, longest first."""
        lengths = {
            key: sum(self.length_m(w) for w in group)
            for key, group in self._by_street(ways).items()
        }
        return sorted(lengths.items(), key=lambda item: -item[1])

    def _only(self, way_ids: set[int], spans: dict[int, set[int]]) -> OsmMap:
        """A copy holding the ways `way_ids` whole, the connectors of `spans` cut to the stretch
        between the first and last node their paths use, and the nodes of both, in the original
        order. Elements that are neither nodes, ways nor relations (bounds, notes) stay."""
        ways: dict[int, ElementTree.Element] = {}
        for element in self._root.iter("way"):
            way_id = int(element.get("id", "0"))
            if way_id in way_ids:
                ways[way_id] = element
            elif way_id in spans:
                ways[way_id] = self._cut(element, spans[way_id])
        nodes = {int(nd.get("ref", "0")) for way in ways.values() for nd in way.iter("nd")}
        root = ElementTree.Element(self._root.tag, self._root.attrib)
        for element in self._root:
            if element.tag == "node":
                if int(element.get("id", "0")) in nodes:
                    root.append(element)
            elif element.tag == "way":
                if int(element.get("id", "0")) in ways:
                    root.append(ways[int(element.get("id", "0"))])
            elif element.tag != "relation":
                root.append(element)
        return OsmMap(root)

    def _cut(self, way: ElementTree.Element, used: set[int]) -> ElementTree.Element:
        refs = [int(nd.get("ref", "0")) for nd in way.iter("nd")]
        first = min(i for i, ref in enumerate(refs) if ref in used)
        last = max(i for i, ref in enumerate(refs) if ref in used)
        cut = copy.deepcopy(way)
        for i, nd in enumerate(list(cut.iter("nd"))):
            if not first <= i <= last:
                cut.remove(nd)
        return cut

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
        joined: _Joined[int] = _Joined()
        ids = sorted(way_ids)
        for way_id in ids:
            first, *rest = self.ways[way_id].nodes
            for node in rest:
                joined.join(first, node)
        groups: dict[int, list[OsmWay]] = defaultdict(list)
        for way_id in ids:
            groups[joined.root(self.ways[way_id].nodes[0])].append(self.ways[way_id])
        pieces = [
            Piece(
                ways=frozenset(w.id for w in ways),
                length_m=sum(self.length_m(w) for w in ways),
                ends=_ends(sorted(set(self._points(ways)))),
            )
            for ways in groups.values()
        ]
        return sorted(pieces, key=lambda p: (-p.length_m, min(p.ways)))

    def coverage(self, edges: Sequence[NetEdge], places: Sequence[LocatedPlace]) -> dict[str, Any]:
        """What a network built from this snapshot covers: its extent, its connected
        components with their ends, the stretches of each street that did not make it into the
        network, and how far the network is from every place located in the run.

        An import keeps the largest component, so a gap between two stretches of a street
        shows as the stretch that is missing, not as a second component."""
        where = {
            j: p for j in NetEdge.junctions(edges) if (p := self._junction_point(j)) is not None
        }
        components = NetEdge.components(edges)
        rows: list[dict[str, Any]] = []
        ends: list[Point] = []
        for members in components[:5]:
            points = [where[j] for j in NetEdge.junctions(members) if j in where]
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
        """The named streets with ways no edge was built from, most missing first, at most 10."""
        built = {w for e in edges for w in e.osm_ways}
        named = (w for w in self.ways.values() if w.name or w.ref)
        rows = []
        for (name, ref, _), ways in self._by_street(named).items():
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
