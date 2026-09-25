"""Pure gold-answer math for the question bank (work-plan E3.2) — no I/O, no SUMO, no DatabaseMCP.

Everything here takes already-fetched `query_edgedata`-shaped mappings (`{edge_id: {measure:
value}}`, DATABASE_MCP_CONTRACT.md §5.4), plain floats, or a plain `NetworkTopology` (the
diagnostic "why"), and returns a classification or a ranked list. Kept separate from
`templates.py` (which does the fetching) so the boundary math — band edges, zero-baseline
handling, cause precedence — has a fast, deterministic unit test (`tests/unit/eval/test_gold.py`).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.answer_value import BottleneckCause
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget

EdgeMeasures = Mapping[str, Mapping[str, float]]


class EdgeMeasure(StrEnum):
    """The DATABASE_MCP_CONTRACT.md §5.4 `query_edgedata` measure names - a closed set, so a
    typo in a measure name fails at call sites, not silently as a `KeyError` inside `gold.py`."""

    SAMPLED_SECONDS = "sampled_seconds"
    DENSITY = "density"
    OCCUPANCY = "occupancy"
    SPEED = "speed"
    WAITING_TIME = "waiting_time"
    TIME_LOSS = "time_loss"
    TRAVEL_TIME = "travel_time"
    ENTERED = "entered"
    LEFT = "left"
    DEPARTED = "departed"
    ARRIVED = "arrived"


class Direction(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    WITHIN_THRESHOLD = "within_threshold"


class MagnitudeBand(StrEnum):
    UNDER_5 = "<5%"
    BETWEEN_5_AND_20 = "5-20%"
    BETWEEN_20_AND_50 = "20-50%"
    OVER_50 = ">50%"


@dataclass(frozen=True, slots=True)
class NetworkTopology:
    """What the "why" rule needs to know about a network (ADR-0029): each edge's (from, to)
    node, the edges each traffic light controls, and the network's known lane drops. Plain data,
    so the rule carries no network of its own and REAL-NET's bank can reuse it unchanged."""

    edge_nodes: Mapping[str, tuple[str, str]]
    tls_controlled_edges: Mapping[str, frozenset[str]]
    lane_drop_edges: frozenset[str]


def mean_edgedata(per_seed: list[EdgeMeasures]) -> dict[str, dict[str, float]]:
    """Averages `query_edgedata` results for the same scenario across its seeds, per edge and
    measure. Edges must be present in every seed's mapping (true here: the network, hence the set
    of known edges, is the same for every seed of a row)."""
    if not per_seed:
        raise ValueError("mean_edgedata requires at least one seed's edgedata")
    edge_ids = per_seed[0].keys()
    return {
        edge_id: {
            measure: sum(seed[edge_id][measure] for seed in per_seed) / len(per_seed)
            for measure in per_seed[0][edge_id]
        }
        for edge_id in edge_ids
    }


def pct_change(baseline: float, value: float) -> float:
    """Signed percent change from `baseline` to `value`. A zero baseline has no defined percent
    change unless `value` is also zero (no change at all) - anything else is reported as an
    unbounded change in `value`'s sign, since "N% more than zero" is not a meaningful number but
    "some" vs "none" still has a clear direction."""
    if baseline == 0.0:
        return 0.0 if value == 0.0 else math.copysign(math.inf, value)
    return (value - baseline) / baseline * 100.0


def classify_direction(baseline: float, value: float, pct_threshold: float = 5.0) -> Direction:
    """DoD §3's own counterfactual template wording - "stay within ±5%" - with `pct_threshold`
    defaulting to that same 5%, based on `pct_change`. `Direction.WITHIN_THRESHOLD` stays
    threshold-agnostic since the threshold itself is a parameter: a fixed `"within_5pct"` member
    would lie about the band actually used whenever a caller passes a different `pct_threshold`."""
    change = pct_change(baseline, value)
    if abs(change) <= pct_threshold:
        return Direction.WITHIN_THRESHOLD
    return Direction.INCREASE if change > 0 else Direction.DECREASE


def magnitude_band(pct_change_value: float) -> MagnitudeBand:
    """One of the four DoD §3 magnitude bands, from a signed or unsigned percent change."""
    magnitude = abs(pct_change_value)
    if magnitude < 5.0:
        return MagnitudeBand.UNDER_5
    if magnitude < 20.0:
        return MagnitudeBand.BETWEEN_5_AND_20
    if magnitude < 50.0:
        return MagnitudeBand.BETWEEN_20_AND_50
    return MagnitudeBand.OVER_50


def bottleneck_causes(
    top_edges: Sequence[str], interventions: Sequence[Intervention], topology: NetworkTopology
) -> list[BottleneckCause]:
    """The gold `BottleneckCause` of each ranked bottleneck edge, in order (ADR-0029 §3; first
    match wins): `intervention` if the edge is an intervention's target edge, feeds it directly
    (ends where it starts) or is controlled by a target traffic light; `merge` if it is a known
    lane drop; `spillback` if it ends where a higher-ranked edge starts; `signal` if a traffic
    light controls it; `demand` otherwise. A `demand_scale` intervention has no target, so it
    never matches: the cause is the local mechanism, more demand only makes it worse."""
    target_edges: set[str] = set()
    target_tls: set[str] = set()
    for intervention in interventions:
        target = intervention.target
        if isinstance(target, EdgeTarget | LaneTarget):
            target_edges.add(target.edge_id)
        elif isinstance(target, TlsTarget):
            target_tls.add(target.tls_id)
    target_start_nodes = {topology.edge_nodes[edge_id][0] for edge_id in target_edges}
    target_tls_edges = set().union(*(topology.tls_controlled_edges[t] for t in target_tls))
    signalised_edges = set().union(*topology.tls_controlled_edges.values())

    causes: list[BottleneckCause] = []
    for rank, edge_id in enumerate(top_edges):
        end_node = topology.edge_nodes[edge_id][1]
        higher_ranked_starts = {topology.edge_nodes[e][0] for e in top_edges[:rank]}
        if (
            edge_id in target_edges
            or end_node in target_start_nodes
            or edge_id in target_tls_edges
        ):
            causes.append(BottleneckCause.INTERVENTION)
        elif edge_id in topology.lane_drop_edges:
            causes.append(BottleneckCause.MERGE)
        elif end_node in higher_ranked_starts:
            causes.append(BottleneckCause.SPILLBACK)
        elif edge_id in signalised_edges:
            causes.append(BottleneckCause.SIGNAL)
        else:
            causes.append(BottleneckCause.DEMAND)
    return causes


def top_bottleneck_edges(edgedata: EdgeMeasures, k: int = 3) -> list[str]:
    """Top-`k` edges by total delay: SUMO's `time_loss` is already summed over every vehicle on
    the edge (vehicle-seconds), i.e. per-vehicle delay × flow, the DoD §3 bottleneck definition.
    Multiplying it by `entered` again would count the flow twice (fixed 2026-09-17)."""
    scored = sorted(edgedata.items(), key=lambda item: item[1][EdgeMeasure.TIME_LOSS], reverse=True)
    return [edge_id for edge_id, _ in scored[:k]]


def top_k_by_delta(
    baseline: EdgeMeasures, intervention: EdgeMeasures, measure: EdgeMeasure, k: int = 5
) -> list[tuple[str, float]]:
    """Top-`k` edges by absolute change in `measure` between `baseline` and `intervention`,
    signed (positive = increase under the intervention)."""
    deltas = {
        edge_id: values[measure] - baseline.get(edge_id, {}).get(measure, 0.0)
        for edge_id, values in intervention.items()
    }
    ranked = sorted(deltas.items(), key=lambda item: abs(item[1]), reverse=True)
    return ranked[:k]


def edges_above_threshold(
    edgedata: EdgeMeasures, measure: EdgeMeasure, threshold: float
) -> list[str]:
    """Edge ids whose `measure` exceeds `threshold`, sorted for a deterministic gold answer."""
    return sorted(edge_id for edge_id, values in edgedata.items() if values[measure] > threshold)
