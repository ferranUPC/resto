"""Ranking of stored scenarios by similarity to a request (DATABASE_MCP_CONTRACT.md §5.3, step 2).

One pure function that every repository backend calls, so the ranking cannot drift between them.
The score is 0.7 x the Jaccard similarity of the intervention signatures plus 0.3 x the Jaccard
similarity of the context tags. `demand_id` plays no part: the ranking is about the shape of
interventions and context on a network, whichever demand was used."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from resto.domain.entities.scenario import Scenario
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import InterventionTarget

_TARGET_ID_ATTR = {"edge": "edge_id", "lane": "lane_id", "tls": "tls_id", "taz": "taz_id"}

_INTERVENTION_WEIGHT = 0.7
_CONTEXT_WEIGHT = 0.3


def _target_signature(target: InterventionTarget | None) -> tuple[str, str]:
    if target is None:
        return ("none", "")
    return (target.kind, getattr(target, _TARGET_ID_ATTR[target.kind]))


def intervention_signature(iv: Intervention) -> tuple[str, str, str, str]:
    target_kind, target_id = _target_signature(iv.target)
    return (iv.type.value, target_kind, target_id, iv.strategy.value)


def _signature_set(interventions: Iterable[Intervention]) -> frozenset[tuple[str, str, str, str]]:
    return frozenset(intervention_signature(iv) for iv in interventions)


def jaccard(a: frozenset[Any], b: frozenset[Any]) -> float:
    """Jaccard similarity; two empty sets are identical (1.0)."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def rank_similar_scenarios(
    candidates: Iterable[Scenario],
    interventions: Iterable[Intervention],
    context_tags: Iterable[str],
    limit: int,
) -> Sequence[tuple[Scenario, float]]:
    """Scores every candidate, drops the zero scores, orders by score descending then by
    `scenario_id` ascending, and keeps the first `limit`."""
    query_signature = _signature_set(interventions)
    query_tags = frozenset(context_tags)
    scored = [
        (
            candidate,
            _INTERVENTION_WEIGHT * jaccard(query_signature, _signature_set(candidate.interventions))
            + _CONTEXT_WEIGHT * jaccard(query_tags, candidate.context_tags),
        )
        for candidate in candidates
    ]
    ranked = sorted(
        (pair for pair in scored if pair[1] > 0), key=lambda pair: (-pair[1], pair[0].scenario_id)
    )
    return ranked[:limit]
