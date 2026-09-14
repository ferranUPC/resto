"""Contract §8 item 2: a repeat `store_*` with identical content is a no-op, and a repeat
`store_*` with different content under an existing id is CONFLICT (§3) - for every aggregate
except `Network`, whose `label` is explicitly allowed to change in place (§3, §5.1)."""

from __future__ import annotations

import dataclasses

import pytest
from tests.unit.domain._samples import demand, expert_note, network, scenario, simulation_result

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.application.ports.errors import ConflictError


def test_storing_the_same_network_twice_is_a_no_op(db: McpClientDatabase) -> None:
    net = network()

    db.networks.store(net)
    db.networks.store(net)

    assert db.networks.get(net.network_id) == net


def test_relabelling_an_existing_network_is_not_a_conflict(db: McpClientDatabase) -> None:
    net = network()
    db.networks.store(net)

    db.networks.store(dataclasses.replace(net, label="new-label"))

    found = db.networks.get(net.network_id)
    assert found is not None and found.label == "new-label"


def test_storing_a_network_with_changed_content_under_the_same_id_conflicts(
    db: McpClientDatabase,
) -> None:
    net = network()
    db.networks.store(net)

    with pytest.raises(ConflictError):
        db.networks.store(dataclasses.replace(net, probe_report=None))


def test_storing_the_same_demand_twice_is_a_no_op(db: McpClientDatabase) -> None:
    net = network()
    db.networks.store(net)
    d = dataclasses.replace(demand(), network_id=net.network_id)

    db.demands.store(d)
    db.demands.store(d)

    assert db.demands.get(d.demand_id) == d


def test_storing_a_demand_with_changed_content_under_the_same_id_conflicts(
    db: McpClientDatabase,
) -> None:
    net = network()
    db.networks.store(net)
    d = dataclasses.replace(demand(), network_id=net.network_id)
    db.demands.store(d)

    with pytest.raises(ConflictError):
        db.demands.store(dataclasses.replace(d, fidelity=None))


def test_storing_the_same_scenario_twice_is_a_no_op(db: McpClientDatabase) -> None:
    s = scenario()

    db.scenarios.store(s)
    db.scenarios.store(s)

    assert db.scenarios.get(s.scenario_id) == s


def test_storing_a_scenario_with_changed_content_under_the_same_id_conflicts(
    db: McpClientDatabase,
) -> None:
    s = scenario()
    db.scenarios.store(s)

    with pytest.raises(ConflictError):
        db.scenarios.store(dataclasses.replace(s, context_tags=frozenset({"different"})))


def test_storing_the_same_result_twice_is_a_no_op(db: McpClientDatabase) -> None:
    result = simulation_result()

    db.results.store(result)
    db.results.store(result)

    assert db.results.get(result.result_id) == result


def test_storing_a_result_with_changed_content_under_the_same_id_conflicts(
    db: McpClientDatabase,
) -> None:
    result = simulation_result()
    db.results.store(result)

    with pytest.raises(ConflictError):
        db.results.store(dataclasses.replace(result, wall_clock_s=999.0))


def test_storing_the_same_note_twice_is_a_no_op(db: McpClientDatabase) -> None:
    note = expert_note()

    db.notes.store(note)
    db.notes.store(note)

    [(found, _score)] = db.notes.search(note.text, note.network_id, {})
    assert found == note


def test_storing_a_note_with_changed_content_under_the_same_id_conflicts(
    db: McpClientDatabase,
) -> None:
    note = expert_note()
    db.notes.store(note)

    with pytest.raises(ConflictError):
        db.notes.store(dataclasses.replace(note, text="a completely different observation"))
