"""Contract §8 item 4 / DoD §4.9: `find_similar_scenario` - exact-hash short-circuit, the scoring
formula (0.7 intervention Jaccard + 0.3 context_tags Jaccard, §5.3), the baseline-matches-baseline
case, `limit`, cross-network isolation. 10 cases."""

from __future__ import annotations

import dataclasses

import pytest
from tests.unit.domain._fixtures import artifact
from tests.unit.domain._samples import scenario as full_scenario

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.domain.entities.scenario import Scenario
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.time_window import TimeWindow


def _lane_closure(edge_id: str, lane_index: int = 1) -> Intervention:
    # Float literals matter here, not just style: `scenario_id_for` hashes via plain
    # `dataclasses.asdict`, which is type-sensitive (0 != 0.0 once JSON-encoded), and every
    # Intervention below crosses a real MCP JSON round trip (`TimeWindow.start`/`end` are typed
    # `float`) before the server recomputes the exact-hash short-circuit - an int literal here
    # would hash differently locally than after that round trip and desync the two.
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id=edge_id, lane_index=lane_index),
        window=TimeWindow(0.0, 3600.0),
    )


def _static_scenario(
    scenario_id: str,
    network_id: str,
    interventions: tuple[Intervention, ...],
    context_tags: frozenset[str],
    demand_id: str = "t1",
) -> Scenario:
    base = full_scenario()
    static = base.mechanisms[0]
    assert isinstance(static, StaticFileMechanism)
    mechanisms = tuple(
        dataclasses.replace(static, path=artifact(f"{scenario_id}.add.xml").path)
        for _ in interventions
    )
    return dataclasses.replace(
        base,
        scenario_id=scenario_id,
        network_id=network_id,
        demand_id=demand_id,
        interventions=interventions,
        mechanisms=mechanisms,
        context_tags=context_tags,
        traci_script=None,
    )


def test_exact_hash_match_short_circuits_over_any_partial_score(db: McpClientDatabase) -> None:
    network_id, interventions, tags = "n1", (_lane_closure("E12"),), frozenset({"peak"})
    exact_id = scenario_id_for(network_id, "t1", interventions, tags)
    exact = dataclasses.replace(
        _static_scenario(exact_id, network_id, interventions, tags), demand_id="t1"
    )
    # A decoy scoring 1.0 under the Jaccard formula too (different demand_id plays no part in
    # scoring) proves the short-circuit really checks the request hash, not "any 1.0 candidate".
    decoy = dataclasses.replace(
        _static_scenario("decoy", network_id, interventions, tags), demand_id="t2"
    )
    db.scenarios.store(exact)
    db.scenarios.store(decoy)

    [match] = db.scenarios.find_similar(network_id, "t1", interventions, tags)

    assert match == (exact, 1.0)


def test_baseline_query_matches_a_stored_baseline_scenario(db: McpClientDatabase) -> None:
    baseline = _static_scenario("baseline", "n1", (), frozenset())
    db.scenarios.store(baseline)

    [(found, score)] = db.scenarios.find_similar("n1", "t1", (), frozenset())

    assert found == baseline
    assert score == 1.0


def test_baseline_scenario_does_not_score_1_against_a_non_empty_query(
    db: McpClientDatabase,
) -> None:
    baseline = _static_scenario("baseline", "n1", (), frozenset())
    db.scenarios.store(baseline)

    [(_found, score)] = db.scenarios.find_similar("n1", "t1", (_lane_closure("E12"),), frozenset())

    assert score < 1.0


def test_scoring_ranks_by_intervention_overlap_only(db: McpClientDatabase) -> None:
    closer = _static_scenario("closer", "n1", (_lane_closure("E12"),), frozenset())
    farther = _static_scenario(
        "farther", "n1", (_lane_closure("E12"), _lane_closure("E50")), frozenset()
    )
    db.scenarios.store(closer)
    db.scenarios.store(farther)

    query = (_lane_closure("E12"), _lane_closure("E99"))
    results = db.scenarios.find_similar("n1", "t1", query, frozenset())

    assert [s.scenario_id for s, _score in results] == ["closer", "farther"]
    assert results[0][1] == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)  # jaccard({E12},{E12,E99})=1/2
    assert results[1][1] == pytest.approx(0.7 * (1 / 3) + 0.3 * 1.0)


def test_scoring_ranks_by_context_tags_overlap_only(db: McpClientDatabase) -> None:
    closer = _static_scenario("closer", "n1", (), frozenset({"peak"}))
    farther = _static_scenario("farther", "n1", (), frozenset({"peak", "rain"}))
    db.scenarios.store(closer)
    db.scenarios.store(farther)

    results = db.scenarios.find_similar("n1", "t1", (), frozenset({"peak", "incident"}))

    assert [s.scenario_id for s, _score in results] == ["closer", "farther"]
    # jaccard(∅,∅) = 1.0 by convention (the baseline-matches-baseline case), so the intervention
    # term is 0.7*1.0 for every candidate here - context_tags is what actually separates them.
    # jaccard({peak},{peak,incident}) = 1/2; jaccard({peak,rain},{peak,incident}) = 1/3
    assert results[0][1] == pytest.approx(0.7 * 1.0 + 0.3 * 0.5)
    assert results[1][1] == pytest.approx(0.7 * 1.0 + 0.3 * (1 / 3))


def test_scoring_combines_intervention_and_context_tags_weights(db: McpClientDatabase) -> None:
    candidate = _static_scenario(
        "candidate", "n1", (_lane_closure("E12"),), frozenset({"peak"})
    )
    db.scenarios.store(candidate)

    [(_found, score)] = db.scenarios.find_similar(
        "n1", "t1", (_lane_closure("E12"),), frozenset({"peak"})
    )

    assert score == pytest.approx(0.7 * 1.0 + 0.3 * 1.0)


def test_zero_score_candidates_are_excluded_not_returned_with_score_zero(
    db: McpClientDatabase,
) -> None:
    # Disjoint interventions AND disjoint context_tags scores exactly 0.0 - the reference
    # implementation's `if score > 0` means that candidate is dropped, not returned at score 0.0.
    disjoint = _static_scenario("disjoint", "n1", (_lane_closure("E1"),), frozenset({"rain"}))
    db.scenarios.store(disjoint)

    results = db.scenarios.find_similar("n1", "t1", (_lane_closure("E2"),), frozenset({"peak"}))

    assert results == []


def test_results_are_scoped_to_one_network(db: McpClientDatabase) -> None:
    interventions, tags = (_lane_closure("E12"),), frozenset[str]()
    same_network = _static_scenario("same-net", "n1", interventions, tags)
    other_network = _static_scenario("other-net", "n2", interventions, tags)
    db.scenarios.store(same_network)
    db.scenarios.store(other_network)

    results = db.scenarios.find_similar("n2", "t1", interventions, tags)

    assert [s.scenario_id for s, _score in results] == ["other-net"]


def test_limit_truncates_the_ranked_results(db: McpClientDatabase) -> None:
    for i in range(5):
        db.scenarios.store(
            _static_scenario(f"s{i}", "n1", (_lane_closure(f"E{i}"),), frozenset())
        )

    results = db.scenarios.find_similar(
        "n1", "t1", (_lane_closure("E999"),), frozenset(), limit=2
    )

    assert len(results) == 2


def test_no_stored_scenarios_on_the_network_returns_empty(db: McpClientDatabase) -> None:
    assert db.scenarios.find_similar("n-empty", "t1", (_lane_closure("E1"),), frozenset()) == []
