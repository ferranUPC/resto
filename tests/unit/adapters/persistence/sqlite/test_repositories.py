"""SQLite reference repositories (E1.3, DATABASE_MCP_CONTRACT.md): idempotency/conflict (§3),
`find_similar_scenario` scoring (§5.3), `query_edgedata` delegation (§5.4), `search_notes`
filtering/ranking (§5.5) - one in-memory DB per test, using the shared domain samples so every
stored entity is a real, invariant-valid instance rather than a hand-rolled shortcut.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from resto.adapters.persistence.sqlite.repositories import (
    SqliteDatabase,
    SqliteDemandRepository,
    SqliteNetworkRepository,
    SqliteNoteRepository,
    SqliteResultRepository,
    SqliteScenarioRepository,
    connect,
)
from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.entities.scenario import Scenario
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.domain._fixtures import artifact
from tests.unit.domain._samples import demand, expert_note, network, scenario, simulation_result

_EDGEDATA_FIXTURE = """<?xml version="1.0"?>
<edgedata>
    <interval begin="0" end="100" id="i1">
        <edge id="E12" sampledSeconds="40" density="10" occupancy="0.1" speed="8"
              waitingTime="1" timeLoss="2" traveltime="10" entered="4" left="4"
              departed="1" arrived="0"/>
    </interval>
</edgedata>
"""


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    c = connect(":memory:")
    yield c
    c.close()


# --- networks: idempotency, label exemption, find() --------------------------------------------


def test_network_store_then_get_round_trips(conn: sqlite3.Connection) -> None:
    repo = SqliteNetworkRepository(conn)
    net = network()

    repo.store(net)

    assert repo.get(net.network_id) == net


def test_network_get_unknown_id_returns_none_not_an_error(conn: sqlite3.Connection) -> None:
    assert SqliteNetworkRepository(conn).get("nope") is None


def test_network_store_is_idempotent_on_identical_content(conn: sqlite3.Connection) -> None:
    repo = SqliteNetworkRepository(conn)
    net = network()

    repo.store(net)
    repo.store(net)  # no-op, not a conflict

    assert repo.get(net.network_id) == net


def test_network_store_different_content_same_id_is_conflict(conn: sqlite3.Connection) -> None:
    repo = SqliteNetworkRepository(conn)
    net = network()
    repo.store(net)

    changed = dataclasses.replace(net, probe_report=None)

    with pytest.raises(ConflictError):
        repo.store(changed)


def test_network_store_same_id_different_label_updates_in_place_not_a_conflict(
    conn: sqlite3.Connection,
) -> None:
    repo = SqliteNetworkRepository(conn)
    net = network()
    repo.store(net)

    relabelled = dataclasses.replace(net, label="a-new-label")
    repo.store(relabelled)

    found = repo.get(net.network_id)
    assert found is not None and found.label == "a-new-label"


def test_network_find_filters_by_label(conn: sqlite3.Connection) -> None:
    repo = SqliteNetworkRepository(conn)
    net = network()
    other = dataclasses.replace(
        net, network_id="other", net_xml=artifact("other.net.xml", "other", "net"), label="other"
    )
    repo.store(net)
    repo.store(other)

    assert [n.network_id for n in repo.find(label=net.label)] == [net.network_id]


def test_network_list_orders_by_id_ascending(conn: sqlite3.Connection) -> None:
    repo = SqliteNetworkRepository(conn)
    net = network()
    other = dataclasses.replace(
        net, network_id="zzz", net_xml=artifact("z.net.xml", "zzz", "net"), label=None
    )
    repo.store(other)
    repo.store(net)  # "abc123" < "zzz"

    assert [n.network_id for n in repo.list()] == [net.network_id, "zzz"]


# --- scenarios: find_similar_scenario scoring (§5.3) --------------------------------------------


def _lane_closure(edge_id: str, lane_index: int = 1) -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id=edge_id, lane_index=lane_index),
        window=TimeWindow(0, 3600),
    )


def _static_scenario(
    scenario_id: str, interventions: tuple[Intervention, ...], context_tags: frozenset[str]
) -> Scenario:
    """A minimal valid Scenario: one StaticFileMechanism per (static) intervention, no script."""
    base = scenario()
    static = base.mechanisms[0]
    assert isinstance(static, StaticFileMechanism)
    mechanisms = tuple(
        dataclasses.replace(static, path=artifact(f"{scenario_id}.add.xml").path)
        for _ in interventions
    )
    return dataclasses.replace(
        base,
        scenario_id=scenario_id,
        interventions=interventions,
        mechanisms=mechanisms,
        context_tags=context_tags,
        traci_script=None,
    )


def test_find_similar_scenario_exact_match_short_circuits_via_the_real_hash(
    conn: sqlite3.Connection
) -> None:
    # A decoy on a *different* demand_id, but with the exact same interventions/context_tags,
    # would also score a coincidental 1.0 under step 2's Jaccard formula (demand_id plays no part
    # in it) - proving the short-circuit genuinely uses the real scenario_id_for(...) hash (not
    # "any candidate that happens to score 1.0") means it must suppress that decoy too.
    repo = SqliteScenarioRepository(conn)
    network_id = "abc123"
    interventions = (_lane_closure("E12"),)
    context_tags = frozenset({"peak"})

    real_id = scenario_id_for(network_id, "t1", interventions, context_tags)
    exact = dataclasses.replace(
        _static_scenario(real_id, interventions, context_tags), demand_id="t1"
    )
    decoy = dataclasses.replace(
        _static_scenario("decoy", interventions, context_tags), demand_id="t2"
    )
    repo.store(exact)
    repo.store(decoy)

    results = repo.find_similar(network_id, "t1", interventions, context_tags)

    assert results == [(exact, 1.0)]


def test_find_similar_scenario_ranks_partial_matches_by_jaccard(conn: sqlite3.Connection) -> None:
    # Neither candidate matches the query exactly, so the score-1.0 short-circuit never fires
    # and both are ranked - that path is covered separately by the "exact match" test above.
    repo = SqliteScenarioRepository(conn)
    closer = _static_scenario("closer", (_lane_closure("E12"),), frozenset())
    farther = _static_scenario(
        "farther", (_lane_closure("E12"), _lane_closure("E50")), frozenset()
    )
    repo.store(closer)
    repo.store(farther)

    query = (_lane_closure("E12"), _lane_closure("E99"))
    results = repo.find_similar(closer.network_id, closer.demand_id, query, frozenset())

    assert [r[0].scenario_id for r in results] == ["closer", "farther"]
    # jaccard({E12}, {E12,E99}) = 1/2; jaccard(context_tags ∅,∅) = 1.0
    assert results[0][1] == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)
    # jaccard({E12,E50}, {E12,E99}) = 1/3
    assert results[1][1] == pytest.approx(0.7 * (1 / 3) + 0.3 * 1.0)


def test_find_similar_scenario_is_scoped_to_one_network(conn: sqlite3.Connection) -> None:
    repo = SqliteScenarioRepository(conn)
    s = scenario()
    other_network = dataclasses.replace(s, scenario_id="s-other-net", network_id="zzz")
    repo.store(s)
    repo.store(other_network)

    results = repo.find_similar("zzz", s.demand_id, s.interventions, s.context_tags)

    assert [r[0].scenario_id for r in results] == ["s-other-net"]


def test_find_similar_scenario_baseline_matches_baseline(conn: sqlite3.Connection) -> None:
    repo = SqliteScenarioRepository(conn)
    baseline = _static_scenario("baseline", (), frozenset())
    repo.store(baseline)

    [(found, score)] = repo.find_similar(baseline.network_id, baseline.demand_id, (), frozenset())

    assert found.scenario_id == "baseline"
    assert score == 1.0


def test_find_similar_scenario_respects_limit(conn: sqlite3.Connection) -> None:
    repo = SqliteScenarioRepository(conn)
    base = scenario()
    for i in range(5):
        repo.store(_static_scenario(f"s{i}", (_lane_closure(f"E{i}"),), frozenset()))

    results = repo.find_similar(
        base.network_id, base.demand_id, (_lane_closure("E999"),), frozenset(), limit=2
    )

    assert len(results) == 2


# --- results: query_edgedata delegation (§5.4) ---------------------------------------------------


def test_query_edgedata_unknown_result_id_raises_not_found(conn: sqlite3.Connection) -> None:
    with pytest.raises(NotFoundError):
        SqliteResultRepository(conn).query_edgedata("nope", [], None)


def test_query_edgedata_result_without_edgedata_artifact_returns_empty(
    conn: sqlite3.Connection
) -> None:
    repo = SqliteResultRepository(conn)
    result = dataclasses.replace(simulation_result(), artifacts=())
    repo.store(result)

    assert repo.query_edgedata(result.result_id, [], None) == {}


def test_query_edgedata_reads_and_aggregates_the_real_artifact(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    edgedata_path = tmp_path / "r.edgedata.xml"
    edgedata_path.write_text(_EDGEDATA_FIXTURE)
    repo = SqliteResultRepository(conn)
    result = dataclasses.replace(
        simulation_result(),
        artifacts=(ArtifactRef(path=edgedata_path, content_hash="ed1", kind="edgedata"),),
    )
    repo.store(result)

    measures = repo.query_edgedata(result.result_id, ["E12"], None)

    assert measures["E12"]["sampled_seconds"] == pytest.approx(40.0)
    assert measures["E12"]["entered"] == 4


# --- notes: search filters + ranking (§5.5) -------------------------------------------------------


class _FixedEmbedder:
    """Test double: exact, hand-picked vectors instead of HashingEmbedder's real hashing -
    isolates search_notes' filtering/ranking plumbing from embedding quality."""

    dimension = 2

    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self._vectors = vectors

    def embed(self, text: str) -> tuple[float, ...]:
        return self._vectors[text]


def test_search_notes_is_scoped_to_one_network(conn: sqlite3.Connection) -> None:
    embedder = _FixedEmbedder(
        {"q": (1.0, 0.0), "note in scope": (1.0, 0.0), "note elsewhere": (1.0, 0.0)}
    )
    repo = SqliteNoteRepository(conn, embedder)
    note = dataclasses.replace(expert_note(), text="note in scope")
    elsewhere = dataclasses.replace(
        expert_note(), note_id="n-2", network_id="other-net", text="note elsewhere"
    )
    repo.store(note)
    repo.store(elsewhere)

    results = repo.search("q", note.network_id, {})

    assert [n.note_id for n, _score in results] == [note.note_id]


def test_search_notes_ranks_by_similarity_descending(conn: sqlite3.Connection) -> None:
    close = dataclasses.replace(expert_note(), note_id="close", text="close")
    far = dataclasses.replace(expert_note(), note_id="far", text="far")
    embedder = _FixedEmbedder({"q": (1.0, 0.0), "close": (1.0, 0.0), "far": (0.0, 1.0)})
    repo = SqliteNoteRepository(conn, embedder)
    repo.store(close)
    repo.store(far)

    results = repo.search("q", close.network_id, {})

    assert [n.note_id for n, _score in results] == ["close", "far"]


def test_search_notes_status_filter_is_applied_before_ranking(conn: sqlite3.Connection) -> None:
    embedder = _FixedEmbedder({"q": (1.0, 0.0), "a": (1.0, 0.0), "b": (1.0, 0.0)})
    repo = SqliteNoteRepository(conn, embedder)
    unverified = dataclasses.replace(expert_note(), note_id="a", text="a")
    confirmed = dataclasses.replace(
        expert_note(), note_id="b", text="b", status=NoteStatus.CONFIRMED
    )
    repo.store(unverified)
    repo.store(confirmed)

    results = repo.search("q", unverified.network_id, {"status": ["confirmed"]})

    assert [n.note_id for n, _score in results] == ["b"]


def test_search_notes_context_tags_filter_requires_all_tags(conn: sqlite3.Connection) -> None:
    embedder = _FixedEmbedder({"q": (1.0, 0.0), "a": (1.0, 0.0), "b": (1.0, 0.0)})
    repo = SqliteNoteRepository(conn, embedder)
    both_tags = dataclasses.replace(
        expert_note(), note_id="a", text="a", context_tags=frozenset({"peak", "rain"})
    )
    one_tag = dataclasses.replace(
        expert_note(), note_id="b", text="b", context_tags=frozenset({"peak"})
    )
    repo.store(both_tags)
    repo.store(one_tag)

    results = repo.search("q", both_tags.network_id, {"context_tags": ["peak", "rain"]})

    assert [n.note_id for n, _score in results] == ["a"]


def test_search_notes_unknown_filter_key_raises_invalid_argument(conn: sqlite3.Connection) -> None:
    repo = SqliteNoteRepository(conn, _FixedEmbedder({"q": (1.0, 0.0)}))

    with pytest.raises(InvalidArgumentError):
        repo.search("q", "abc123", {"nonexistent_filter": ["x"]})


def test_update_note_status_persists_the_new_status(conn: sqlite3.Connection) -> None:
    embedder = _FixedEmbedder({"the text": (1.0, 0.0)})
    repo = SqliteNoteRepository(conn, embedder)
    note = dataclasses.replace(expert_note(), text="the text")
    repo.store(note)

    repo.update_status(note.note_id, NoteStatus.CONFIRMED)

    [(found, _score)] = repo.search("the text", note.network_id, {})
    assert found.status is NoteStatus.CONFIRMED


def test_update_note_status_unknown_id_raises_not_found(conn: sqlite3.Connection) -> None:
    repo = SqliteNoteRepository(conn, _FixedEmbedder({}))

    with pytest.raises(NotFoundError):
        repo.update_status("nope", NoteStatus.CONFIRMED)


def test_note_store_different_text_same_id_is_conflict(conn: sqlite3.Connection) -> None:
    embedder = _FixedEmbedder({"a": (1.0, 0.0), "b": (0.0, 1.0)})
    repo = SqliteNoteRepository(conn, embedder)
    note = dataclasses.replace(expert_note(), text="a")
    repo.store(note)

    with pytest.raises(ConflictError):
        repo.store(dataclasses.replace(note, text="b"))


# --- demands: idempotency + network scoping -------------------------------------------------------


def test_demand_list_is_scoped_to_one_network(conn: sqlite3.Connection) -> None:
    repo = SqliteDemandRepository(conn)
    d = demand()
    other_network = dataclasses.replace(
        d, demand_id="d2", network_id="other", trips=artifact("t2.xml", "d2", "trips")
    )
    repo.store(d)
    repo.store(other_network)

    assert [x.demand_id for x in repo.list(d.network_id)] == [d.demand_id]


# --- SqliteDatabase wiring -----------------------------------------------------------------------


def test_sqlite_database_wires_every_repository(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "resto.db")
    try:
        net = network()
        db.networks.store(net)
        assert db.networks.get(net.network_id) == net
    finally:
        db.close()
