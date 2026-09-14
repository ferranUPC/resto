"""Contract §8 item 1: round-trip fidelity for all five aggregates, every optional field both
populated and absent, through a real MCP `store_*`/`get_*` round trip."""

from __future__ import annotations

import dataclasses

from tests.unit.domain._fixtures import artifact, static_intervention
from tests.unit.domain._samples import demand, expert_note, network, scenario, simulation_result

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.domain.entities.expert_note import Provenance
from resto.domain.value_objects.mechanism import StaticFileMechanism


def test_network_round_trips_fully_populated(db: McpClientDatabase) -> None:
    net = network()

    db.networks.store(net)

    assert db.networks.get(net.network_id) == net


def test_network_round_trips_with_optional_fields_absent(db: McpClientDatabase) -> None:
    net = dataclasses.replace(network(), probe_report=None, label=None)

    db.networks.store(net)

    assert db.networks.get(net.network_id) == net


def test_demand_round_trips_fully_populated(db: McpClientDatabase) -> None:
    net = network()
    db.networks.store(net)
    d = dataclasses.replace(demand(), network_id=net.network_id)

    db.demands.store(d)

    assert db.demands.get(d.demand_id) == d


def test_demand_round_trips_with_optional_fields_absent(db: McpClientDatabase) -> None:
    net = network()
    db.networks.store(net)
    d = dataclasses.replace(
        demand(),
        network_id=net.network_id,
        sources=(),
        fidelity=None,
        calibration_rounds=(),
        derived_from=None,
    )

    db.demands.store(d)

    assert db.demands.get(d.demand_id) == d


def test_scenario_round_trips_fully_populated(db: McpClientDatabase) -> None:
    s = scenario()

    db.scenarios.store(s)

    assert db.scenarios.get(s.scenario_id) == s


def test_scenario_round_trips_with_optional_fields_absent(db: McpClientDatabase) -> None:
    # A ScriptMechanism (present in the fully-populated sample) requires a traci_script, so the
    # "everything optional stripped" case needs a scenario built with only a static mechanism.
    s = dataclasses.replace(
        scenario(),
        scenario_id="s-minimal",
        interventions=(static_intervention(),),
        mechanisms=(StaticFileMechanism(file_kind="rerouter", path=artifact("r.add.xml").path),),
        additional_files=(),
        context_tags=frozenset(),
        traci_script=None,
    )

    db.scenarios.store(s)

    assert db.scenarios.get(s.scenario_id) == s


def test_simulation_result_round_trips_fully_populated(db: McpClientDatabase) -> None:
    result = simulation_result()

    db.results.store(result)

    assert db.results.get(result.result_id) == result


def test_simulation_result_round_trips_with_optional_fields_absent(db: McpClientDatabase) -> None:
    result = dataclasses.replace(
        simulation_result(), artifacts=(), applied_actions=(), wall_clock_s=None
    )

    db.results.store(result)

    assert db.results.get(result.result_id) == result


def test_expert_note_round_trips_fully_populated(db: McpClientDatabase) -> None:
    note = expert_note()

    db.notes.store(note)

    [(found, _score)] = db.notes.search(note.text, note.network_id, {})
    assert found == note


def test_expert_note_round_trips_with_optional_fields_absent(db: McpClientDatabase) -> None:
    note = dataclasses.replace(
        expert_note(), provenance=Provenance.OPINION, scenario_id=None, context_tags=frozenset()
    )

    db.notes.store(note)

    [(found, _score)] = db.notes.search(note.text, note.network_id, {})
    assert found == note
