from __future__ import annotations

from dataclasses import replace

import pytest

from resto.domain.services.scenario_similarity import jaccard, rank_similar_scenarios
from tests.unit.domain._samples import scenario


def test_jaccard_of_two_empty_sets_is_one() -> None:
    assert jaccard(frozenset(), frozenset()) == 1.0


def test_jaccard_is_intersection_over_union() -> None:
    assert jaccard(frozenset({1, 2}), frozenset({2, 3})) == pytest.approx(1 / 3)


def test_ranking_weights_interventions_seventy_and_context_thirty() -> None:
    base = scenario()
    bare = replace(base, interventions=(), mechanisms=(), traci_script=None)
    only_tags = replace(bare, scenario_id="tags")

    [(found, score)] = rank_similar_scenarios([only_tags], (), base.context_tags, limit=10)

    assert found.scenario_id == "tags"
    assert score == pytest.approx(0.7 * 1.0 + 0.3 * 1.0)


def test_ranking_orders_by_score_then_scenario_id_and_keeps_limit() -> None:
    base = replace(scenario(), interventions=(), mechanisms=(), traci_script=None)
    candidates = [replace(base, scenario_id=i) for i in ("b", "a", "c")]

    ranked = rank_similar_scenarios(candidates, (), base.context_tags, limit=2)

    assert [s.scenario_id for s, _ in ranked] == ["a", "b"]
