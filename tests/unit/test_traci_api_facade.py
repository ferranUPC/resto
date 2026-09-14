"""resto.traci_api (E1.2): the facade Builder scripts import must stay a thin re-export.

See src/resto/traci_api.py's docstring and docs/adr/0005 - a persisted script's import statement
must keep resolving even if adapters/sumo/traci_api.py is refactored underneath it.
"""

from __future__ import annotations

from resto import traci_api as facade
from resto.adapters.sumo import traci_api as real


def test_facade_exports_every_public_primitive_and_declarative_name() -> None:
    assert set(facade.__all__) == {
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
    }


def test_facade_names_are_the_same_objects_as_the_real_implementation() -> None:
    for name in facade.__all__:
        assert getattr(facade, name) is getattr(real, name)
