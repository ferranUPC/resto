"""`demand_scale` regeneration (work-plan E2.3; architecture §2.2, §2.4): deterministic code, no
agent — the Scenario Builder agent only decides *that* a `demand_scale` intervention needs this
mechanism (`adapters/llm/agents/scenario_builder.py`'s system prompt), the actual resampling and
re-routing is plain code, the same split as `run_simulation`'s Simulation Runner (CLAUDE.md
"Agents share one port").

`demand_id = trips.content_hash` (the `Demand` entity's own invariant) makes this idempotent for
free: an existing derived demand for the same (trips, factor) pair is returned unrun, without a
second `duarouter` call — the same "zero redundant work" shape as `run_simulation`, just keyed on
content rather than a request hash because `Demand` is a content-hashed aggregate (architecture
§1's identity policy).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from resto.application.ports.repositories import DemandRepository
from resto.application.ports.sumo import DemandScaler, DemandTools
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network


def scale_demand(
    demand: Demand,
    network: Network,
    factor: float,
    *,
    scaler: DemandScaler,
    duarouter: DemandTools,
    demands: DemandRepository,
    out_dir: Path,
) -> Demand:
    """Resamples `demand`'s trips by `factor` and re-routes them over `network`.

    Raises:
        ValueError: `factor` is not positive, or `demand.network_id != network.network_id`.
    """
    if demand.network_id != network.network_id:
        raise ValueError(
            f"demand {demand.demand_id!r} belongs to network {demand.network_id!r}, "
            f"not {network.network_id!r}"
        )

    new_trips = scaler.scale(demand.trips, factor, out_dir)
    demand_id = new_trips.content_hash
    existing = demands.get(demand_id)
    if existing is not None:
        return existing

    new_routes = duarouter.duarouter(network.net_xml, new_trips, demand.spec.seed, out_dir)
    derived = Demand(
        demand_id=demand_id,
        network_id=network.network_id,
        spec=replace(demand.spec, scale=demand.spec.scale * factor),
        trips=new_trips,
        routes=new_routes,
        derived_from=demand.demand_id,
    )
    demands.store(derived)
    return derived
