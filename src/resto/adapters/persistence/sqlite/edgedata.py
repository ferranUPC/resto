"""Parses a SUMO `--edgedata-output` XML file and aggregates it over a window
(DATABASE_MCP_CONTRACT.md §5.4) — the one non-trivial piece of `query_edgedata`.

"An edge id absent from the network is omitted" (§5.4) needs a definition of "the network" that
doesn't require this module to know about `NetworkRepository`/`sumolib` at all: SUMO's own
`--edgedata-output` lists every network edge in every interval by default, including zero-traffic
ones (verified against `eval/dev-net/demand/_runs/*.edgedata.xml`: exactly DEV-NET's 80 non-
internal edges appear, sampled or not) — so "known to the network" here means "appears in at
least one interval of this file", with no extra coupling needed.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

# contract snake_case -> SUMO's own meandata attribute name
_RATE_OR_MEAN_ATTRS = {
    "density": "density",
    "occupancy": "occupancy",
    "speed": "speed",
    "waiting_time": "waitingTime",
    "time_loss": "timeLoss",
    "travel_time": "traveltime",
}
_COUNTER_ATTRS = {
    "entered": "entered",
    "left": "left",
    "departed": "departed",
    "arrived": "arrived",
}

Interval = tuple[float, float, dict[str, dict[str, float]]]  # (begin, end, {edge_id: {attr: v}})


def _parse_intervals(path: Path) -> list[Interval]:
    root = ET.parse(path).getroot()
    intervals: list[Interval] = []
    for interval_el in root.findall("interval"):
        begin = float(interval_el.get("begin", 0.0))
        end = float(interval_el.get("end", 0.0))
        edges: dict[str, dict[str, float]] = {}
        for edge_el in interval_el.findall("edge"):
            edge_id = edge_el.get("id", "")
            if edge_id.startswith(":"):  # internal junction edge
                continue
            values = {
                attr: float(edge_el.get(sumo_attr, 0.0))
                for attr, sumo_attr in {**_RATE_OR_MEAN_ATTRS, **_COUNTER_ATTRS}.items()
            }
            values["sampled_seconds"] = float(edge_el.get("sampledSeconds", 0.0))
            edges[edge_id] = values
        intervals.append((begin, end, edges))
    return intervals


def _round_half_up(x: float) -> float:
    return math.floor(x + 0.5)


def _overlap_fraction(ibegin: float, iend: float, wbegin: float, wend: float) -> float:
    overlap = min(iend, wend) - max(ibegin, wbegin)
    duration = iend - ibegin
    if overlap <= 0 or duration <= 0:
        return 0.0
    return min(overlap, duration) / duration


def _aggregate_edge(
    intervals: Sequence[Interval], edge_id: str, window: tuple[float, float] | None
) -> dict[str, float]:
    total_weight = 0.0
    weighted_sum = dict.fromkeys(_RATE_OR_MEAN_ATTRS, 0.0)
    counter_sum = dict.fromkeys(_COUNTER_ATTRS, 0.0)

    for begin, end, edges in intervals:
        values = edges.get(edge_id)
        if values is None:
            continue
        fraction = 1.0 if window is None else _overlap_fraction(begin, end, window[0], window[1])
        if fraction <= 0:
            continue
        weight = values["sampled_seconds"] * fraction
        total_weight += weight
        for attr in _RATE_OR_MEAN_ATTRS:
            weighted_sum[attr] += values[attr] * weight
        for attr in _COUNTER_ATTRS:
            counter_sum[attr] += values[attr] * fraction

    result: dict[str, float] = {"sampled_seconds": total_weight}
    for attr in _RATE_OR_MEAN_ATTRS:
        result[attr] = weighted_sum[attr] / total_weight if total_weight > 0 else 0.0
    for attr in _COUNTER_ATTRS:
        result[attr] = _round_half_up(counter_sum[attr])
    return result


def query_edgedata(
    path: Path, edge_ids: Sequence[str], window: tuple[float, float] | None
) -> dict[str, dict[str, float]]:
    """See DATABASE_MCP_CONTRACT.md §5.4. `path` is one SimulationResult's edgedata artifact."""
    intervals = _parse_intervals(path)
    known_edges = {edge_id for _begin, _end, edges in intervals for edge_id in edges}
    requested = list(edge_ids) if edge_ids else sorted(known_edges)
    return {
        edge_id: _aggregate_edge(intervals, edge_id, window)
        for edge_id in requested
        if edge_id in known_edges
    }
