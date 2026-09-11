"""Identity policy: request hashes for Scenario / SimulationResult, UUIDs for events.
Network and Demand ids are content hashes of their main artifact (see the entities)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import asdict

from resto.domain.constants import SUMO_VERSION
from resto.domain.services.content_hash import compute_content_hash
from resto.domain.value_objects.intervention import Intervention


def scenario_id_for(
    network_id: str,
    demand_id: str,
    interventions: Iterable[Intervention],
    context_tags: Iterable[str],
) -> str:
    return compute_content_hash(
        "scenario",
        network_id,
        demand_id,
        [asdict(i) for i in interventions],
        sorted(context_tags),
    )


def result_id_for(scenario_id: str, seed: int, mode: str, sumo_version: str = SUMO_VERSION) -> str:
    return compute_content_hash("result", scenario_id, seed, mode, sumo_version)


def new_id() -> str:
    return uuid.uuid4().hex
