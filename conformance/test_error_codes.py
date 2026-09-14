"""Contract §8 item 8: at least one case per error code (§7), and every `get_*` returns `null`
for an unknown id rather than raising. `INTERNAL` is deliberately not exercised here: §7 reserves
it for genuinely unexpected failures, which by design cannot be triggered through valid contract
inputs - forcing one would mean reaching past the black-box `db.*` surface this suite is scoped
to (see `conftest.py`)."""

from __future__ import annotations

import dataclasses

import pytest
from tests.unit.domain._samples import demand, expert_note, network, scenario, simulation_result

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.domain.entities.expert_note import NoteStatus


def test_store_network_with_changed_content_raises_conflict(db: McpClientDatabase) -> None:
    net = network()
    db.networks.store(net)

    with pytest.raises(ConflictError):
        db.networks.store(dataclasses.replace(net, probe_report=None))


def test_update_note_status_of_an_unknown_note_raises_not_found(db: McpClientDatabase) -> None:
    with pytest.raises(NotFoundError):
        db.notes.update_status("nope", NoteStatus.CONFIRMED)


def test_query_edgedata_of_an_unknown_result_raises_not_found(db: McpClientDatabase) -> None:
    with pytest.raises(NotFoundError):
        db.results.query_edgedata("nope", [], None)


def test_search_notes_with_an_unknown_filter_key_raises_invalid_argument(
    db: McpClientDatabase,
) -> None:
    note = expert_note()
    db.notes.store(note)

    with pytest.raises(InvalidArgumentError):
        db.notes.search("q", note.network_id, {"nonexistent_filter": ["x"]})


def test_get_network_of_an_unknown_id_returns_none_not_an_exception(
    db: McpClientDatabase,
) -> None:
    assert db.networks.get("nope") is None


def test_get_demand_of_an_unknown_id_returns_none_not_an_exception(db: McpClientDatabase) -> None:
    assert db.demands.get("nope") is None


def test_get_scenario_of_an_unknown_id_returns_none_not_an_exception(
    db: McpClientDatabase,
) -> None:
    assert db.scenarios.get("nope") is None


def test_get_result_of_an_unknown_id_returns_none_not_an_exception(db: McpClientDatabase) -> None:
    assert db.results.get("nope") is None


def test_store_functions_are_unaffected_by_prior_errors(db: McpClientDatabase) -> None:
    """A conformant server must not corrupt session/connection state on an error path - the next
    unrelated call must still succeed."""
    with pytest.raises(NotFoundError):
        db.notes.update_status("nope", NoteStatus.CONFIRMED)

    net = network()
    d = dataclasses.replace(demand(), network_id=net.network_id)
    s = scenario()
    result = simulation_result()
    db.networks.store(net)
    db.demands.store(d)
    db.scenarios.store(s)
    db.results.store(result)

    assert db.networks.get(net.network_id) == net
    assert db.demands.get(d.demand_id) == d
    assert db.scenarios.get(s.scenario_id) == s
    assert db.results.get(result.result_id) == result
