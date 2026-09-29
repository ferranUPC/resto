"""Which aggregates may be combined: a `Demand` is routed over one `Network`, so it fits only it."""

from __future__ import annotations

from resto.domain.entities.demand import Demand


def ensure_demand_on_network(demand: Demand, network_id: str, *, label: str = "demand") -> None:
    """Raises `ValueError` naming both networks when `demand` was built for another one."""
    if demand.network_id != network_id:
        raise ValueError(
            f"{label} {demand.demand_id!r} belongs to network {demand.network_id!r}, "
            f"not {network_id!r}"
        )
