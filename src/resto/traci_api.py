"""Stable public import path for Scenario Builder scripts (ADR-0005, `lint_script`'s AST check).

`from resto.traci_api import close_lane, when, run` is the *only* surface a persisted script is
allowed to depend on - never `resto.adapters.sumo.traci_api` directly. The real implementation
lives there and is free to be refactored; this module is the two-line promise that a script's
import statement keeps working no matter what happens underneath (same reason `NetworkQuery`
shields callers from `SumolibNetworkQuery` - see docs/adr/0009 - except here the caller being
shielded is a script on disk, not application/ code).
"""

from resto.adapters.sumo.traci_api import (
    applied_actions,
    at_time,
    close,
    close_lane,
    get_edge_occupancy,
    get_edge_speed,
    get_vehicle_count,
    open_lane,
    registered_rules,
    run,
    set_speed,
    set_tls_program,
    start,
    step,
    when,
)

__all__ = [
    "applied_actions",
    "at_time",
    "close",
    "close_lane",
    "get_edge_occupancy",
    "get_edge_speed",
    "get_vehicle_count",
    "open_lane",
    "registered_rules",
    "run",
    "set_speed",
    "set_tls_program",
    "start",
    "step",
    "when",
]
