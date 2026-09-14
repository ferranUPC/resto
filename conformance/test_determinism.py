"""Contract §8 item 7 / §6: every listing, called twice with no state change in between, returns
identical order - a backend cannot depend on e.g. undefined dict/hash-map iteration order or a
storage engine's natural row order."""

from __future__ import annotations

import dataclasses

from tests.unit.domain._samples import demand, expert_note, network

from resto.adapters.persistence.mcp_client import McpClientDatabase


def test_list_networks_is_deterministic_across_repeated_calls(db: McpClientDatabase) -> None:
    for i in range(5):
        db.networks.store(
            dataclasses.replace(
                network(),
                network_id=f"net-{i}",
                net_xml=dataclasses.replace(network().net_xml, content_hash=f"net-{i}"),
                label=f"label-{i}",
            )
        )

    first = [n.network_id for n in db.networks.list()]
    second = [n.network_id for n in db.networks.list()]

    assert first == second
    assert len(first) == 5


def test_list_demands_is_deterministic_across_repeated_calls(db: McpClientDatabase) -> None:
    net = network()
    db.networks.store(net)
    for i in range(4):
        base = demand()
        trips = dataclasses.replace(base.trips, content_hash=f"trip-{i}")
        db.demands.store(
            dataclasses.replace(
                base, demand_id=f"trip-{i}", network_id=net.network_id, trips=trips
            )
        )

    first = [d.demand_id for d in db.demands.list(net.network_id)]
    second = [d.demand_id for d in db.demands.list(net.network_id)]

    assert first == second
    assert len(first) == 4


def test_search_notes_ordering_is_deterministic_across_repeated_calls(
    db: McpClientDatabase,
) -> None:
    base = expert_note()
    for i in range(4):
        db.notes.store(dataclasses.replace(base, note_id=f"n-{i}", text=f"note body {i}"))

    first = [n.note_id for n, _score in db.notes.search("note body", base.network_id, {})]
    second = [n.note_id for n, _score in db.notes.search("note body", base.network_id, {})]

    assert first == second
    assert len(first) == 4
