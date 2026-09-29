"""Repository contract (DATABASE_MCP_CONTRACT.md §3, §5; ADR-0012, ADR-0031): every rule below is
stated once and runs unchanged against the in-memory and the SQLite backend, through the repository
protocols only. A backend that answers differently from the SQLite reference fails here, not in
production. Backend-specific detail (SQL, the connection) stays in `sqlite/test_repositories.py`."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from resto.adapters.embedding.hashing import HashingEmbedder
from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryNoteRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
)
from resto.adapters.persistence.sqlite.repositories import (
    SqliteDemandRepository,
    SqliteNetworkRepository,
    SqliteNoteRepository,
    SqliteResultRepository,
    SqliteScenarioRepository,
    connect,
)
from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.domain._fixtures import artifact
from tests.unit.domain._samples import demand, expert_note, network, scenario, simulation_result


@dataclass
class Backend:
    networks: NetworkRepository
    demands: DemandRepository
    scenarios: ScenarioRepository
    results: ResultRepository
    notes: NoteRepository


@pytest.fixture(params=["memory", "sqlite"])
def db(request: pytest.FixtureRequest) -> Iterator[Backend]:
    if request.param == "memory":
        yield Backend(
            InMemoryNetworkRepository(),
            InMemoryDemandRepository(),
            InMemoryScenarioRepository(),
            InMemoryResultRepository(),
            InMemoryNoteRepository(),
        )
        return
    conn: sqlite3.Connection = connect(":memory:")
    yield Backend(
        SqliteNetworkRepository(conn),
        SqliteDemandRepository(conn),
        SqliteScenarioRepository(conn),
        SqliteResultRepository(conn),
        SqliteNoteRepository(conn, HashingEmbedder()),
    )
    conn.close()


def _network_named(network_id: str, source: str = "dev-net.osm") -> Network:
    base = network()
    return replace(
        base,
        network_id=network_id,
        net_xml=artifact(f"{network_id}.net.xml", network_id, "net"),
        recipe=replace(base.recipe, source=NetworkSource(kind="file", value=source)),
        label=None,
    )


def _derived_from(base: Network, network_id: str, label: str) -> Network:
    return replace(
        _network_named(network_id),
        recipe=NetworkRecipe(base_network_id=base.network_id),
        derived_from=base.network_id,
        label=label,
    )


def _demand_named(demand_id: str, network_id: str | None = None) -> Demand:
    base = demand()
    return replace(
        base,
        demand_id=demand_id,
        network_id=network_id or base.network_id,
        trips=artifact(f"{demand_id}.trips.xml", demand_id, "trips"),
    )


# --- networks -------------------------------------------------------------------------------------


def test_network_store_then_get_round_trips(db: Backend) -> None:
    db.networks.store(network())

    assert db.networks.get(network().network_id) == network()


def test_network_get_unknown_id_returns_none(db: Backend) -> None:
    assert db.networks.get("nope") is None


def test_network_store_is_idempotent_on_identical_content(db: Backend) -> None:
    db.networks.store(network())

    db.networks.store(network())

    assert db.networks.get(network().network_id) == network()


def test_network_store_same_id_different_label_updates_in_place(db: Backend) -> None:
    db.networks.store(network())

    db.networks.store(replace(network(), label="renamed"))

    stored = db.networks.get(network().network_id)
    assert stored is not None and stored.label == "renamed"


def test_network_store_different_content_same_id_is_conflict(db: Backend) -> None:
    db.networks.store(network())

    with pytest.raises(ConflictError):
        db.networks.store(replace(network(), probe_report=None))


def test_network_list_orders_by_id_not_by_insertion(db: Backend) -> None:
    db.networks.store(_network_named("zzz"))
    db.networks.store(_network_named("aaa"))

    assert [n.network_id for n in db.networks.list()] == ["aaa", "zzz"]


def test_network_find_by_source_excludes_other_sources(db: Backend) -> None:
    db.networks.store(_network_named("a", source="one.osm"))
    db.networks.store(_network_named("b", source="two.osm"))

    found = db.networks.find(source="two.osm")

    assert [n.network_id for n in found] == ["b"]


def test_network_find_by_derived_from_and_label(db: Backend) -> None:
    base = replace(network(), label="base")
    derived = _derived_from(base, "derived", "child")
    db.networks.store(base)
    db.networks.store(derived)

    assert [n.network_id for n in db.networks.find(derived_from=base.network_id)] == ["derived"]
    assert [n.network_id for n in db.networks.find(label="base")] == [base.network_id]
    assert db.networks.find(derived_from=base.network_id, label="base") == []


def test_network_find_without_filters_lists_all_ordered_by_id(db: Backend) -> None:
    db.networks.store(_network_named("zzz"))
    db.networks.store(_network_named("aaa"))

    assert [n.network_id for n in db.networks.find()] == ["aaa", "zzz"]


# --- demands --------------------------------------------------------------------------------------


def test_demand_store_is_idempotent_and_conflict_on_different_content(db: Backend) -> None:
    db.demands.store(demand())
    db.demands.store(demand())

    with pytest.raises(ConflictError):
        db.demands.store(replace(demand(), routes=replace(demand().routes, content_hash="x")))


def test_demand_list_is_scoped_to_one_network_and_ordered_by_id(db: Backend) -> None:
    db.demands.store(_demand_named("zzz"))
    db.demands.store(_demand_named("aaa"))
    db.demands.store(_demand_named("other", network_id="elsewhere"))

    assert [d.demand_id for d in db.demands.list(demand().network_id)] == ["aaa", "zzz"]


# --- scenarios ------------------------------------------------------------------------------------


def _lane_closure(edge_id: str) -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id=edge_id, lane_index=1),
        window=TimeWindow(0, 3600),
    )


def _static_scenario(
    scenario_id: str, interventions: tuple[Intervention, ...], context_tags: frozenset[str]
) -> Scenario:
    base = scenario()
    static = base.mechanisms[0]
    assert isinstance(static, StaticFileMechanism)
    mechanisms = tuple(
        replace(static, path=artifact(f"{scenario_id}.add.xml").path) for _ in interventions
    )
    return replace(
        base,
        scenario_id=scenario_id,
        interventions=interventions,
        mechanisms=mechanisms,
        context_tags=context_tags,
        traci_script=None,
    )


def test_scenario_store_is_idempotent_and_conflict_on_different_content(db: Backend) -> None:
    db.scenarios.store(scenario())
    db.scenarios.store(scenario())

    with pytest.raises(ConflictError):
        db.scenarios.store(replace(scenario(), content_hash="different"))


def test_scenario_get_unknown_id_returns_none(db: Backend) -> None:
    assert db.scenarios.get("nope") is None


def test_find_similar_exact_identity_short_circuits_via_the_real_hash(db: Backend) -> None:
    interventions = (_lane_closure("E12"),)
    tags = frozenset({"peak"})
    real_id = scenario_id_for("abc123", "t1", interventions, tags)
    exact = replace(_static_scenario(real_id, interventions, tags), demand_id="t1")
    decoy = replace(_static_scenario("decoy", interventions, tags), demand_id="t2")
    db.scenarios.store(exact)
    db.scenarios.store(decoy)

    assert db.scenarios.find_similar("abc123", "t1", interventions, tags) == [(exact, 1.0)]


def test_find_similar_ranks_by_weighted_jaccard_and_not_by_insertion(db: Backend) -> None:
    farther = _static_scenario("farther", (_lane_closure("E12"), _lane_closure("E50")), frozenset())
    closer = _static_scenario("closer", (_lane_closure("E12"),), frozenset())
    db.scenarios.store(farther)  # stored first, so insertion order would put it first
    db.scenarios.store(closer)

    query = (_lane_closure("E12"), _lane_closure("E99"))
    results = db.scenarios.find_similar("abc123", "t1", query, frozenset())

    assert [s.scenario_id for s, _ in results] == ["closer", "farther"]
    assert results[0][1] == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)
    assert results[1][1] == pytest.approx(0.7 * (1 / 3) + 0.3 * 1.0)


def test_find_similar_breaks_score_ties_by_scenario_id(db: Backend) -> None:
    for scenario_id in ("b", "a", "c"):
        db.scenarios.store(_static_scenario(scenario_id, (_lane_closure("E1"),), frozenset()))

    results = db.scenarios.find_similar("abc123", "t1", (_lane_closure("E1"),), frozenset())

    assert [s.scenario_id for s, _ in results] == ["a", "b", "c"]


def test_find_similar_drops_zero_scores(db: Backend) -> None:
    db.scenarios.store(_static_scenario("unrelated", (_lane_closure("E7"),), frozenset({"night"})))

    results = db.scenarios.find_similar("abc123", "t1", (_lane_closure("E1"),), frozenset({"peak"}))

    assert results == []


def test_find_similar_is_scoped_to_one_network(db: Backend) -> None:
    base = scenario()
    db.scenarios.store(base)
    db.scenarios.store(replace(base, scenario_id="s-other-net", network_id="zzz"))

    results = db.scenarios.find_similar(
        "zzz", base.demand_id, base.interventions, base.context_tags
    )

    assert [s.scenario_id for s, _ in results] == ["s-other-net"]


def test_find_similar_baseline_matches_baseline_with_full_score(db: Backend) -> None:
    baseline = _static_scenario("baseline", (), frozenset())
    db.scenarios.store(baseline)

    [(found, score)] = db.scenarios.find_similar("abc123", "t1", (), frozenset())

    assert found.scenario_id == "baseline"
    assert score == 1.0


def test_find_similar_respects_limit(db: Backend) -> None:
    for i in range(5):
        db.scenarios.store(_static_scenario(f"s{i}", (_lane_closure(f"E{i}"),), frozenset()))

    results = db.scenarios.find_similar(
        "abc123", "t1", (_lane_closure("E999"),), frozenset(), limit=2
    )

    assert len(results) == 2


# --- results --------------------------------------------------------------------------------------


def test_result_existing_id_identical_content_is_a_no_op(db: Backend) -> None:
    result = simulation_result()
    db.results.store(result)

    db.results.store(result)

    assert db.results.get(result.result_id) == result


def test_result_existing_id_different_content_is_conflict(db: Backend) -> None:
    result = simulation_result()
    db.results.store(result)
    changed = replace(result, wall_clock_s=(result.wall_clock_s or 0.0) + 1.0)

    with pytest.raises(ConflictError):
        db.results.store(changed)

    assert db.results.get(result.result_id) == result  # the original is untouched


def test_result_list_is_scoped_to_one_scenario_and_ordered_by_id(db: Backend) -> None:
    base = simulation_result()
    db.results.store(replace(base, result_id="zzz"))
    db.results.store(replace(base, result_id="aaa"))
    db.results.store(replace(base, result_id="other", scenario_id="elsewhere"))

    assert [r.result_id for r in db.results.list(base.scenario_id)] == ["aaa", "zzz"]


_EDGEDATA = """<?xml version="1.0"?>
<edgedata>
    <interval begin="0" end="100" id="i1">
        <edge id="E1" sampledSeconds="40" density="10" occupancy="0.1" speed="8"
              waitingTime="1" timeLoss="2" traveltime="10" entered="4" left="4"
              departed="1" arrived="0"/>
        <edge id=":J1_0" sampledSeconds="99" density="99" occupancy="0" speed="0"
              waitingTime="0" timeLoss="0" traveltime="0" entered="0" left="0"
              departed="0" arrived="0"/>
    </interval>
    <interval begin="100" end="200" id="i2">
        <edge id="E1" sampledSeconds="60" density="20" occupancy="0.3" speed="12"
              waitingTime="3" timeLoss="4" traveltime="20" entered="6" left="5"
              departed="0" arrived="1"/>
    </interval>
</edgedata>
"""


def _store_result_with_edgedata(db: Backend, tmp_path: Path) -> str:
    path = tmp_path / "r.edgedata.xml"
    path.write_text(_EDGEDATA)
    result = replace(
        simulation_result(),
        artifacts=(ArtifactRef(path=path, content_hash="ed1", kind="edgedata"),),
    )
    db.results.store(result)
    return result.result_id


def test_query_edgedata_unknown_result_raises_not_found(db: Backend) -> None:
    with pytest.raises(NotFoundError):
        db.results.query_edgedata("nope", [], None)


def test_query_edgedata_result_without_edgedata_artifact_returns_empty(db: Backend) -> None:
    result = replace(simulation_result(), artifacts=())
    db.results.store(result)

    assert db.results.query_edgedata(result.result_id, [], None) == {}


def test_query_edgedata_over_the_whole_run_weights_by_sampled_seconds(
    db: Backend, tmp_path: Path
) -> None:
    result_id = _store_result_with_edgedata(db, tmp_path)

    measures = db.results.query_edgedata(result_id, ["E1"], None)

    assert measures["E1"]["sampled_seconds"] == pytest.approx(100.0)
    assert measures["E1"]["speed"] == pytest.approx((8 * 40 + 12 * 60) / 100)
    assert measures["E1"]["entered"] == 10


def test_query_edgedata_window_clips_intervals_and_prorates_counters(
    db: Backend, tmp_path: Path
) -> None:
    result_id = _store_result_with_edgedata(db, tmp_path)

    measures = db.results.query_edgedata(result_id, ["E1"], (0.0, 150.0))

    # second interval contributes half: weights 40 and 30, counters 4 + 3, left 4 + 2.5 -> 7
    assert measures["E1"]["sampled_seconds"] == pytest.approx(70.0)
    assert measures["E1"]["speed"] == pytest.approx((8 * 40 + 12 * 30) / 70)
    assert measures["E1"]["entered"] == 7
    assert measures["E1"]["left"] == 7
    assert measures["E1"]["waiting_time"] == pytest.approx(2.5)  # vehicle-seconds: prorated only


def test_query_edgedata_omits_unknown_and_internal_edges(db: Backend, tmp_path: Path) -> None:
    result_id = _store_result_with_edgedata(db, tmp_path)

    measures = db.results.query_edgedata(result_id, ["E1", "NOPE", ":J1_0"], None)

    assert list(measures) == ["E1"]


# --- notes ----------------------------------------------------------------------------------------


def test_note_store_is_idempotent_and_conflict_on_different_text(db: Backend) -> None:
    db.notes.store(expert_note())
    db.notes.store(expert_note())

    with pytest.raises(ConflictError):
        db.notes.store(replace(expert_note(), text="a different claim"))


def test_search_notes_is_scoped_to_one_network(db: Backend) -> None:
    note = expert_note()
    db.notes.store(note)
    db.notes.store(replace(note, note_id="n-other", network_id="elsewhere"))

    found = db.notes.search(note.text, note.network_id, {})

    assert [n.note_id for n, _ in found] == [note.note_id]


def test_search_notes_ranks_the_matching_text_first(db: Backend) -> None:
    note = expert_note()
    db.notes.store(replace(note, note_id="n-unrelated", text="completely unrelated words here"))
    db.notes.store(note)

    found = db.notes.search(note.text, note.network_id, {})

    assert found[0][0].note_id == note.note_id
    assert found[0][1] >= found[-1][1]


def test_search_notes_filters_by_status_and_requires_all_context_tags(db: Backend) -> None:
    note = expert_note()
    confirmed = replace(note, note_id="n-c", status=NoteStatus.CONFIRMED)
    db.notes.store(note)
    db.notes.store(confirmed)

    by_status = db.notes.search(note.text, note.network_id, {"status": ["confirmed"]})
    by_tags = db.notes.search(note.text, note.network_id, {"context_tags": ["peak", "rain"]})

    assert [n.note_id for n, _ in by_status] == ["n-c"]
    assert by_tags == []


def test_search_notes_unknown_filter_key_is_invalid_argument(db: Backend) -> None:
    with pytest.raises(InvalidArgumentError):
        db.notes.search("q", "abc123", {"bogus": 1})


def test_update_note_status_persists_the_new_status(db: Backend) -> None:
    note = expert_note()
    db.notes.store(note)

    db.notes.update_status(note.note_id, NoteStatus.CONFIRMED)

    found = db.notes.search(note.text, note.network_id, {"status": ["confirmed"]})
    assert [n.note_id for n, _ in found] == [note.note_id]


def test_update_note_status_unknown_id_raises_not_found(db: Backend) -> None:
    with pytest.raises(NotFoundError):
        db.notes.update_status("nope", NoteStatus.CONFIRMED)
