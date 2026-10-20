"""An OpenStreetMap snapshot read as data, for the tools that look into it before and after
`netconvert` (ADR-0046). `OsmMap` lists the streets of a snapshot and selects some of them into a
derived snapshot; `OsmMap.coverage` compares a built network with the snapshot it came from.

A `.osm` file and a `.net.xml` are read with the stdlib XML parser, as `network_import` already
counts the edges of a `.net.xml`; no port stands in front of them.

- **A street** is the highways that share a `name` and a `ref`; highways with neither are grouped
  by their class (`primary_link`, `service`).
- **A selection** keeps the roads whose name contains one of the given names, or whose `ref` is
  one of the given refs, and every road with a node in one of the given areas (cut to the stretch
  inside), plus the connectors the caller asks for (`Connectors`), minus what the drop rules
  remove (ADR-0047). A zone keeps whole the roundabouts and the ramps (`*_link`) it touches
  (E6.1/13). Footways, paths, cycleways and the like are never selected, whatever their name, and
  nothing but highways is kept: the rail profile finds no railway in a selection.
- **A piece** is a set of ways joined by shared nodes, whatever their direction. Its ends are the
  two points farthest apart, found in two sweeps (exact on a corridor, close enough on anything
  else).
- **A trace** is the quickest road between two points (`OsmMap.trace`): the roads of the snapshot
  as a graph with one arc per pair of consecutive nodes, in the directions the way allows, each
  costing its length over its speed. It reads the road the way a driver would, whatever names it
  takes on the way, and tells which streets to select to keep it.
"""

from __future__ import annotations

import copy
import hashlib
import heapq
import math
import re
from collections import defaultdict
from collections.abc import Hashable, Iterable, Sequence, Set
from dataclasses import dataclass
from itertools import combinations, groupby, pairwise
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

MAX_LINK_REACH_M = 600.0
"""Farthest, counted outside the zone, that a zone follows a chain of `*_link` ways from the one it
touches: more than the 434 m ramp of the Sant Just exit, less than a 764 m `trunk_link` that is
a road of its own."""

_NOT_ROADS = frozenset(
    {"footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "corridor", "track"}
    | {"platform", "proposed", "construction", "elevator"}
)
"""Highway classes a car never drives on: never selected and never a connector."""

MAX_LISTED = 40
"""Rows a listing returns at most, longest first; the rest are counted."""

DEFAULT_KMH = {
    "motorway": 120.0,
    "trunk": 100.0,
    "primary": 50.0,
    "secondary": 40.0,
    "tertiary": 30.0,
    "unclassified": 25.0,
    "residential": 20.0,
    "service": 15.0,
    "living_street": 10.0,
    "motorway_link": 60.0,
    "trunk_link": 50.0,
    "primary_link": 40.0,
    "secondary_link": 35.0,
    "tertiary_link": 25.0,
}
"""Speed of a road with no numeric `maxspeed`, by class, in km/h. It falls with every step down
the classes, so that a trace prefers the higher road when the two are equally long. SUMO's own
typemap is no use here: it gives trunk, primary and secondary roads the same 100 km/h."""

UNKNOWN_KMH = 20.0
"""Speed of a road whose class is not in `DEFAULT_KMH`."""

PREFERRED_COST = 0.8
"""What a road the user named costs in a trace, as a share of its time: the named street wins
when two roads take about as long."""

MAX_SNAP_M = 500.0
"""Farthest a trace moves a point to put it on a road: a hospital's grounds or a square, not the
next district."""

SUGGESTED_SHARE = 0.1
"""Share of a trace a street must cover to be suggested for the selection; the access road from
a building does not."""

MIN_ZONE_M = 10.0
MAX_ZONE_M = 5000.0
"""Smallest and largest `radius_m` of a zone (`list_streets`, `select_streets`)."""

ZONE_MARGIN_M = 50.0
"""What a zone a trace suggests adds to the reach of its stretch, so that the ends and the
junctions next to them are inside."""

_MAIN_CLASSES = frozenset(
    {"motorway", "trunk", "primary", "secondary", "tertiary"}
    | {"motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
)
"""Classes whose unnamed stretches a trace suggests as a zone: the access to a building
(`service`, `residential`, `living_street`, `unclassified`) does not deserve one."""

_MPH = 1.609344
_MAXSPEED = re.compile(r"(\d+(?:\.\d+)?)\s*(mph)?")
_ONE_WAY_CLASSES = frozenset({"motorway", "motorway_link"})


@dataclass(frozen=True, slots=True)
class OsmWay:
    id: int
    nodes: tuple[int, ...]
    highway: str
    name: str
    ref: str
    oneway: Literal[-1, 0, 1] = 0
    """1 when the way is driven only along its nodes, -1 only against them, 0 both ways."""
    maxspeed_kmh: float | None = None
    roundabout: bool = False
    """The way is (a part of) a roundabout: `junction=roundabout`."""

    @staticmethod
    def tagged(way_id: int, nodes: tuple[int, ...], tags: dict[str, str]) -> OsmWay:
        return OsmWay(
            id=way_id,
            nodes=nodes,
            highway=tags["highway"],
            name=tags.get("name", ""),
            ref=tags.get("ref", ""),
            oneway=OsmWay._oneway(tags),
            maxspeed_kmh=OsmWay._maxspeed(tags.get("maxspeed", "")),
            roundabout=tags.get("junction") == "roundabout",
        )

    @staticmethod
    def _oneway(tags: dict[str, str]) -> Literal[-1, 0, 1]:
        value = tags.get("oneway", "")
        if value == "-1":
            return -1
        if value in ("yes", "1", "true"):
            return 1
        if value == "no":
            return 0
        implied = tags.get("junction") == "roundabout" or tags["highway"] in _ONE_WAY_CLASSES
        return 1 if implied else 0

    @staticmethod
    def _maxspeed(value: str) -> float | None:
        """km/h from a `maxspeed` tag: '50' or '30 mph'; None for anything else ('signals')."""
        match = _MAXSPEED.fullmatch(value.strip())
        if match is None:
            return None
        return float(match[1]) * (_MPH if match[2] else 1.0)

    @property
    def tagged_refs(self) -> tuple[str, ...]:
        """The `ref` tag holds several refs separated by ';' (e.g. 'N-340;B-23')."""
        return tuple(r.strip() for r in self.ref.split(";") if r.strip())

    @property
    def refs(self) -> frozenset[str]:
        return frozenset(r.casefold() for r in self.tagged_refs)

    @property
    def speed_kmh(self) -> float:
        if self.maxspeed_kmh is not None:
            return self.maxspeed_kmh
        return DEFAULT_KMH.get(self.highway, UNKNOWN_KMH)

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
class Area:
    """A circle: the same `near` and `radius_m` that `OsmMap.streets` takes."""

    near: Point
    radius_m: float

    def holds(self, point: Point) -> bool:
        return distance_m(self.near, point) <= self.radius_m

    def as_json(self) -> dict[str, Any]:
        return {"near": rounded(self.near), "radius_m": round(self.radius_m)}


@dataclass(frozen=True, slots=True)
class DropRule:
    """Roads a selection gives up: those whose name contains one of `names`, whose ref is one of
    `refs` or whose `highway` class is one of `classes`; inside `area` only, when it has one."""

    names: tuple[str, ...] = ()
    refs: tuple[str, ...] = ()
    classes: tuple[str, ...] = ()
    area: Area | None = None

    def as_json(self) -> dict[str, Any]:
        row: dict[str, Any] = {"names": list(self.names), "refs": list(self.refs)}
        row["classes"] = list(self.classes)
        row["area"] = self.area.as_json() if self.area else None
        return row


@dataclass(frozen=True, slots=True)
class Piece:
    """Ways joined by shared nodes: how long they are and where they end."""

    ways: frozenset[int]
    length_m: float
    ends: tuple[Point, Point]

    def as_json(self) -> dict[str, Any]:
        return {"length_m": round(self.length_m), "ends": [rounded(p) for p in self.ends]}


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
            nodes = tuple(int(nd.get("ref", "0")) for nd in element.iter("nd"))
            self.ways[way_id] = OsmWay.tagged(way_id, nodes, tags)

    @staticmethod
    def read(snapshot: Path) -> OsmMap:
        return OsmMap(ElementTree.parse(snapshot).getroot())

    def length_m(self, way: OsmWay) -> float:
        return _path_m(self._points([way]))

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
        None): name, ref, classes, length and extent, longest first. With `near`, a way counts
        only for its stretch between the first and the last node inside, the stretch a zone
        keeps (`select`)."""
        area = Area(near, radius_m) if near is not None else None
        rows = []
        for (name, ref, _), ways in self._by_street(self.ways.values()).items():
            stretches = [(w, s) for w in ways if (s := self._stretch(w, area))]
            if not stretches:
                continue
            rows.append(
                {
                    "name": name,
                    "ref": ref,
                    "classes": sorted({w.highway for w, _ in stretches}),
                    "length_m": round(sum(_path_m(s) for _, s in stretches)),
                    "extent": extent([p for _, s in stretches for p in s]),
                }
            )
        return sorted(rows, key=lambda r: (-r["length_m"], r["name"], r["ref"]))

    def _stretch(self, way: OsmWay, area: Area | None) -> list[Point]:
        """The points of the way, or those between its first and last node inside `area`; empty
        when it has no node there."""
        points = [(n, self.nodes[n]) for n in way.nodes if n in self.nodes]
        if area is not None:
            inside = [i for i, (_, p) in enumerate(points) if area.holds(p)]
            points = points[inside[0] : inside[-1] + 1] if inside else []
        return [p for _, p in points]

    # -- selecting --------------------------------------------------------------------------

    def select(
        self,
        names: Sequence[str],
        refs: Sequence[str],
        connectors: Connectors,
        areas: Sequence[Area] = (),
        drop: Sequence[DropRule] = (),
    ) -> tuple[OsmMap, dict[str, Any]]:
        """The snapshot with only the matching roads, the roads inside `areas` (cut to the stretch
        inside), the connectors asked for and none of what `drop` removes, and a summary of what
        was kept. What a rule removes does not come back as a connector.

        Raises:
            ValueError: nothing to match, a rule with no criterion, or nothing left.
        """
        wanted_names = [n.strip().casefold() for n in names if n.strip()]
        wanted_refs = {r.strip().casefold() for r in refs if r.strip()}
        if not wanted_names and not wanted_refs and not areas:
            raise ValueError("give at least one name, ref or area to select")
        rules = [_normalized(rule) for rule in drop]
        matched = {
            w.id for w in self.ways.values() if w.is_road and _matches(w, wanted_names, wanted_refs)
        }
        inside = {id_: self._inside(area) for id_, area in enumerate(areas)}
        cuts = self._area_cuts(inside, matched)
        if not matched and not cuts:
            raise ValueError(
                f"no road in the snapshot has a name containing any of {list(names)} or a "
                f"ref in {list(refs)}, or lies in the areas given: call list_streets to see "
                "the names and refs there are, or try another spelling or area"
            )
        conserved = self._only(matched, cuts)
        banned_by = [self._removed_by(rule) for rule in rules]
        banned = set().union(*banned_by)
        removed = [ids & conserved.ways.keys() for ids in banned_by]
        gone = banned & conserved.ways.keys()
        kept = matched - gone
        kept_cuts = {w: nodes for w, nodes in cuts.items() if w not in gone}
        if not kept and not kept_cuts:
            raise ValueError("the drop rules remove every road of the selection: relax them")
        touched = [set(found) - matched - banned for found in inside.values()]
        completions = [
            self._completion(area, ways, banned) for area, ways in zip(areas, touched, strict=True)
        ]
        completed = set().union(*completions) - kept
        base = self._only(kept | completed, kept_cuts)
        spans = self._connectors(base, banned, connectors)
        selected = self._only(kept | completed, {**kept_cuts, **spans})
        stretches = self._only(set(), kept_cuts)
        joining = [selected.ways[w] for w in sorted(spans)]
        pieces = selected.pieces(selected.ways)
        summary = {
            "streets": [
                {"name": name, "ref": ref, "length_m": round(length)}
                for (name, ref, _), length in selected._lengths([selected.ways[w] for w in kept])
            ],
            "areas": [
                self._contribution(area, stretches, kept_cuts, inside[i], completions[i], kept)
                for i, area in enumerate(areas)
            ],
            "dropped": [
                {**rule.as_json(), **conserved._size([conserved.ways[w] for w in removed[i]])}
                for i, rule in enumerate(rules)
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

    def _inside(self, area: Area) -> dict[int, set[int]]:
        """For every road with a node in `area`, the nodes of it that are."""
        found: dict[int, set[int]] = {}
        for way in self.ways.values():
            if not way.is_road:
                continue
            nodes = {n for n in way.nodes if n in self.nodes and area.holds(self.nodes[n])}
            if nodes:
                found[way.id] = nodes
        return found

    def _area_cuts(
        self, inside: dict[int, dict[int, set[int]]], matched: set[int]
    ) -> dict[int, set[int]]:
        """The roads of the areas that no name or ref keeps whole, each with its nodes inside any
        area. A road with one node inside has no stretch to keep."""
        cuts: dict[int, set[int]] = defaultdict(set)
        for found in inside.values():
            for way_id, nodes in found.items():
                if way_id not in matched:
                    cuts[way_id] |= nodes
        return {
            w: nodes
            for w, nodes in sorted(cuts.items())
            if len({i for i, n in enumerate(self.ways[w].nodes) if n in nodes}) > 1
        }

    def _removed_by(self, rule: DropRule) -> set[int]:
        """Every road of the snapshot the rule removes; a road is in the area when any node of
        the whole road is."""
        names = list(rule.names)
        refs = set(rule.refs)
        inside = self._inside(rule.area) if rule.area else None
        return {
            w.id
            for w in self.ways.values()
            if (_matches(w, names, refs) or w.highway in rule.classes)
            and (inside is None or w.id in inside)
        }

    def _contribution(
        self,
        area: Area,
        stretches: OsmMap,
        cuts: dict[int, set[int]],
        inside: dict[int, set[int]],
        completion: dict[int, float],
        whole: set[int],
    ) -> dict[str, Any]:
        """What the area added to the selection: its roads that no name or ref kept, by class and
        cut to the stretch inside (`stretches`), and apart what it completed outside its circle."""
        ways = [stretches.ways[w] for w in sorted(cuts) if w in inside]
        by_class = {
            cls: stretches._size([w for w in ways if w.highway == cls])
            for cls in sorted({w.highway for w in ways})
        }
        added = [m for w, m in completion.items() if w not in whole and m > 0]
        completed = {"ways": len(added), "length_m": round(sum(added))}
        return {
            **area.as_json(),
            **stretches._size(ways),
            "by_class": by_class,
            "completed": completed,
        }

    def _completion(self, area: Area, touched: set[int], banned: set[int]) -> dict[int, float]:
        """The ways a zone completes, each with the metres of it outside the zone: the whole
        roundabout of every way of `touched` that is one, and every `*_link` way of `touched`
        whole, followed along the `*_link` ways that continue it up to `MAX_LINK_REACH_M` outside
        the zone. A way in `banned` is never one."""
        found = self._rings(touched, banned) | self._link_chains(area, touched, banned)
        return {w: self._outside_m(self.ways[w], area) for w in found}

    def _rings(self, touched: set[int], banned: set[int]) -> set[int]:
        """The roundabout ways joined by shared nodes to a roundabout way of `touched`."""
        at_node: dict[int, list[int]] = defaultdict(list)
        for way in self.ways.values():
            if way.roundabout and way.is_road and way.id not in banned:
                for node in way.nodes:
                    at_node[node].append(way.id)
        found: set[int] = set()
        pending = [w for w in sorted(touched) if self.ways[w].roundabout]
        while pending:
            way_id = pending.pop()
            if way_id in found:
                continue
            found.add(way_id)
            pending.extend(w for n in self.ways[way_id].nodes for w in at_node[n])
        return found

    def _link_chains(self, area: Area, touched: set[int], banned: set[int]) -> set[int]:
        """Every `*_link` way of `touched`, and the `*_link` ways that continue one from an end
        node, while the metres outside `area` along the chain, this way included, stay within
        `MAX_LINK_REACH_M`: a shortest path over the ways, so the order does not matter."""
        links = {
            w.id: w
            for w in self.ways.values()
            if w.highway.endswith("_link") and w.is_road and w.id not in banned
        }
        at_end: dict[int, list[int]] = defaultdict(list)
        for way in links.values():
            at_end[way.nodes[0]].append(way.id)
            at_end[way.nodes[-1]].append(way.id)
        reach = {w: self._outside_m(links[w], area) for w in sorted(touched) if w in links}
        queue = [(m, w) for w, m in reach.items()]
        heapq.heapify(queue)
        while queue:
            metres, way_id = heapq.heappop(queue)
            if metres > reach[way_id]:
                continue
            for end in (links[way_id].nodes[0], links[way_id].nodes[-1]):
                for nxt in at_end[end]:
                    total = metres + self._outside_m(links[nxt], area)
                    if total <= MAX_LINK_REACH_M and total < reach.get(nxt, float("inf")):
                        reach[nxt] = total
                        heapq.heappush(queue, (total, nxt))
        return set(reach)

    def _outside_m(self, way: OsmWay, area: Area) -> float:
        """Metres of the way on pairs of consecutive nodes that are not both inside `area`."""
        points = [self.nodes[n] for n in way.nodes if n in self.nodes]
        return sum(
            distance_m(a, b) for a, b in pairwise(points) if not (area.holds(a) and area.holds(b))
        )

    def _size(self, ways: Sequence[OsmWay]) -> dict[str, Any]:
        return {"ways": len(ways), "length_m": round(sum(self.length_m(w) for w in ways))}

    def _connectors(
        self, base: OsmMap, banned: set[int], connectors: Connectors
    ) -> dict[int, set[int]]:
        """The other roads on a path of at most `MAX_CONNECTOR_M` between two pieces of `base`
        (the selection so far), each with the nodes of it the path uses: a shortest path from
        every node of `base` at once, labelled with its piece; an arc whose two ends were reached
        from different pieces closes such a path. A road in `banned` is never one."""
        if connectors == "none":
            return {}
        piece_of = {
            n: i
            for i, p in enumerate(base.pieces(base.ways))
            for w in p.ways
            for n in base.ways[w].nodes
        }
        arcs: dict[int, list[tuple[int, float, int]]] = defaultdict(list)
        for way in self.ways.values():
            if way.id in base.ways or way.id in banned or not way.is_road:
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

    # -- tracing ----------------------------------------------------------------------------

    def trace(
        self,
        start: Point,
        end: Point,
        prefer: Sequence[str] = (),
        by: Literal["time", "length"] = "time",
    ) -> dict[str, Any] | Unreached:
        """The quickest road from `start` to `end` (the shortest with `by="length"`): its
        stretches, how long it is, where each point was put on a road, and the streets to select
        to keep it, with the first and last node on them. The roads whose name contains one of
        `prefer` or whose ref is one of them cost `PREFERRED_COST` of their time.

        Each point goes to the nearest node from which a car can reach the other point, at most
        `MAX_SNAP_M` away; when there is none, the trace is `Unreached` at that point.

        Raises:
            ValueError: both points go to the same node.
        """
        arcs = self._driving_arcs()
        back: dict[int, list[int]] = defaultdict(list)
        for out in arcs.values():
            for step in out:
                back[step.end].append(step.start)
        near_end = [
            n for n in set(arcs) | set(back) if distance_m(end, self.nodes[n]) <= MAX_SNAP_M
        ]
        if not near_end:
            return Unreached(end)
        source = min(
            self._reaching(near_end, back), key=lambda n: (distance_m(start, self.nodes[n]), n)
        )
        if distance_m(start, self.nodes[source]) > MAX_SNAP_M:
            return Unreached(start)
        terms = [p.strip().casefold() for p in prefer if p.strip()]
        steps = self._cheapest(source, end, arcs, by, terms)
        if not steps:
            raise ValueError(
                f"both points are nearest to the same node {rounded(self.nodes[source])}: "
                "give two places apart"
            )
        return self._corridor(steps, start, end, terms)

    def _driving_arcs(self) -> dict[int, list[_Step]]:
        """For every node of a road, the steps a car can drive from it."""
        arcs: dict[int, list[_Step]] = defaultdict(list)
        for way in self.ways.values():
            if not way.is_road:
                continue
            for a, b in pairwise(way.nodes):
                if a in self.nodes and b in self.nodes:
                    length = distance_m(self.nodes[a], self.nodes[b])
                    if way.oneway >= 0:
                        arcs[a].append(_Step(a, b, way, length))
                    if way.oneway <= 0:
                        arcs[b].append(_Step(b, a, way, length))
        return arcs

    @staticmethod
    def _reaching(targets: Iterable[int], back: dict[int, list[int]]) -> set[int]:
        """The nodes from which a car reaches one of `targets`, the targets included."""
        seen = set(targets)
        stack = list(seen)
        while stack:
            for previous in back.get(stack.pop(), ()):
                if previous not in seen:
                    seen.add(previous)
                    stack.append(previous)
        return seen

    def _cheapest(
        self,
        source: int,
        end: Point,
        arcs: dict[int, list[_Step]],
        by: Literal["time", "length"],
        terms: Sequence[str],
    ) -> list[_Step]:
        """Dijkstra from `source` to every node it reaches, by time or by length; the steps to
        the node nearest `end`. A user's term may be a name or a ref, so it is matched as both."""
        refs = set(terms)

        def cost(step: _Step) -> float:
            spent = step.length_m if by == "length" else step.minutes
            return spent * (PREFERRED_COST if _matches(step.way, terms, refs) else 1.0)

        spent: dict[int, float] = {source: 0.0}
        came_from: dict[int, _Step] = {}
        queue = [(0.0, source)]
        while queue:
            reached, node = heapq.heappop(queue)
            if reached > spent[node]:
                continue
            for step in arcs.get(node, ()):
                total = reached + cost(step)
                if total < spent.get(step.end, float("inf")):
                    spent[step.end], came_from[step.end] = total, step
                    heapq.heappush(queue, (total, step.end))
        target = min(spent, key=lambda n: distance_m(end, self.nodes[n]))
        steps = []
        while target in came_from:
            steps.append(came_from[target])
            target = came_from[target].start
        return steps[::-1]

    def _corridor(
        self, steps: list[_Step], start: Point, end: Point, terms: Sequence[str]
    ) -> dict[str, Any]:
        total = sum(s.length_m for s in steps)
        selection = self._suggested(steps, total, terms)
        names = [n.casefold() for n in selection["names"]]
        refs = {r.casefold() for r in selection["refs"]}
        on_selection = [s for s in steps if _matches(s.way, names, refs)]
        route = []
        for (name, ref, highway), group in groupby(
            steps, key=lambda s: (s.way.name, s.way.ref, s.way.highway)
        ):
            stretch = list(group)
            route.append(
                {
                    "name": name,
                    "ref": ref,
                    "class": highway,
                    "length_m": round(sum(s.length_m for s in stretch)),
                    "from": rounded(self.nodes[stretch[0].start]),
                    "to": rounded(self.nodes[stretch[-1].end]),
                }
            )
        return {
            "route": route,
            "total_m": round(total),
            "minutes": round(sum(s.minutes for s in steps), 1),
            "snapped": [
                {
                    "point": rounded(point),
                    "node_at": rounded(self.nodes[node]),
                    "distance_m": round(distance_m(point, self.nodes[node])),
                }
                for point, node in ((start, steps[0].start), (end, steps[-1].end))
            ],
            "joins_at": rounded(self.nodes[on_selection[0].start]) if on_selection else None,
            "leaves_at": rounded(self.nodes[on_selection[-1].end]) if on_selection else None,
            "suggested_selection": selection,
        }

    def _suggested(
        self, steps: Sequence[_Step], total_m: float, terms: Sequence[str]
    ) -> dict[str, Any]:
        """The streets to select to keep a trace: by name those that cover `SUGGESTED_SHARE` of
        it; by ref those that do and carry no name somewhere or several names; the streets of
        the user's `terms` the trace touches; and a zone for each stretch of roads with neither
        name nor ref (ramps, roundabouts), whatever its share."""
        by_name: dict[str, float] = defaultdict(float)
        by_ref: dict[str, float] = defaultdict(float)
        names_of_ref: dict[str, set[str]] = defaultdict(set)
        for step in steps:
            if step.way.name:
                by_name[step.way.name] += step.length_m
            for ref in step.way.tagged_refs:
                by_ref[ref] += step.length_m
                names_of_ref[ref].add(step.way.name)
        enough = SUGGESTED_SHARE * total_m
        names = [n for n, length in sorted(by_name.items()) if length >= enough]
        refs = [
            r
            for r, length in sorted(by_ref.items())
            if length >= enough and ("" in names_of_ref[r] or len(names_of_ref[r]) > 1)
        ]
        names.sort(key=lambda n: -by_name[n])
        refs.sort(key=lambda r: -by_ref[r])
        for step in steps:
            if _matches(step.way, terms, frozenset()) and step.way.name not in names:
                names.append(step.way.name)
            refs += [r for r in step.way.tagged_refs if r.casefold() in terms and r not in refs]
        return {
            "names": names,
            "refs": refs,
            "connectors": "links",
            "areas": [z.as_json() for z in self._zones(steps)],
        }

    def _zones(self, steps: Sequence[_Step]) -> list[Area]:
        """One circle for each run of consecutive steps on unnamed, ref-less roads of the main
        classes, around its points; circles that overlap become one that holds both."""
        groups: list[list[Point]] = []
        for unnamed, run in groupby(steps, key=_is_unnamed_main):
            if unnamed:
                stretch = list(run)
                groups.append([self.nodes[stretch[0].start]] + [self.nodes[s.end] for s in stretch])
        circles = [(_circle(points), points) for points in groups]
        merged = True
        while merged:
            merged = False
            for i, j in combinations(range(len(circles)), 2):
                (a, points_a), (b, points_b) = circles[i], circles[j]
                if distance_m(a.near, b.near) <= a.radius_m + b.radius_m:
                    points = points_a + points_b
                    circles[i] = (_circle(points), points)
                    del circles[j]
                    merged = True
                    break
        return [circle for circle, _ in circles]

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
                    "ends": [rounded(p) for p in component_ends],
                }
            )
        return {
            "extent": extent(list(where.values())) if where else None,
            "components": len(components),
            "largest_components": rows,
            "streets_with_missing_stretches": self._missing(edges),
            "places": [
                {
                    "query": place.query,
                    "point": rounded((place.lat, place.lon)),
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


@dataclass(frozen=True, slots=True)
class _Step:
    """One arc of a trace: from node `start` to node `end` along `way`."""

    start: int
    end: int
    way: OsmWay
    length_m: float

    @property
    def minutes(self) -> float:
        # metres over km/h, times 3.6 / 60, is minutes
        return self.length_m / self.way.speed_kmh * 0.06


@dataclass(frozen=True, slots=True)
class Unreached:
    """A trace that could not start or end: no road within `MAX_SNAP_M` of `point` joins it to
    the other point."""

    point: Point


def _normalized(rule: DropRule) -> DropRule:
    """The rule with blanks removed and names, refs and classes casefolded.

    Raises:
        ValueError: it has no name, ref or class to match.
    """
    names = tuple(n.strip().casefold() for n in rule.names if n.strip())
    refs = tuple(r.strip().casefold() for r in rule.refs if r.strip())
    classes = tuple(c.strip().casefold() for c in rule.classes if c.strip())
    if not (names or refs or classes):
        raise ValueError("a drop rule needs at least one name, ref or class to remove")
    return DropRule(names, refs, classes, rule.area)


def _matches(way: OsmWay, names: Sequence[str], refs: Set[str]) -> bool:
    """Whether the way's name contains one of `names` or it has one of `refs` (both
    casefolded)."""
    return any(n in way.name.casefold() for n in names) or bool(way.refs & refs)


def _is_unnamed_main(step: _Step) -> bool:
    return not step.way.name and not step.way.ref and step.way.highway in _MAIN_CLASSES


def _circle(points: Sequence[Point]) -> Area:
    """The circle around the middle of the points' box that holds them all, with a margin;
    `radius_m` stays within `MIN_ZONE_M` and `MAX_ZONE_M`."""
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    centre = ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)
    reach = max(distance_m(centre, p) for p in points) + ZONE_MARGIN_M
    return Area(centre, min(MAX_ZONE_M, max(MIN_ZONE_M, math.ceil(reach))))


def _path_m(points: Sequence[Point]) -> float:
    return sum(distance_m(a, b) for a, b in pairwise(points))


def _ends(points: Sequence[Point]) -> tuple[Point, Point]:
    """The two points farthest apart, by two sweeps from the first point."""
    first = max(points, key=lambda p: distance_m(points[0], p))
    second = max(points, key=lambda p: distance_m(first, p))
    return first, second


def extent(points: Sequence[Point]) -> dict[str, float]:
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    return {
        "south": round(min(lats), 5),
        "west": round(min(lons), 5),
        "north": round(max(lats), 5),
        "east": round(max(lons), 5),
    }


def _nearest(point: Point, others: Sequence[Point]) -> int | None:
    return round(min(distance_m(point, p) for p in others)) if others else None


def rounded(point: Point) -> list[float]:
    return [round(point[0], 5), round(point[1], 5)]
