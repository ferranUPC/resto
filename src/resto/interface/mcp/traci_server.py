"""TraciMCP server exposing the traci_api primitives (DoD §4.9, work-plan E1.2, Stretch per
architecture §2.4/ADR-0009 - a future live agent).

Thin driving adapter (ADR-0009): only the 8 primitives are exposed, not `at_time`/`when`/`run` -
those take Python callables as arguments, which cannot cross the MCP wire as JSON. A registered
declarative rule only ever makes sense for a script executed in-process by the Simulation Runner.

Run directly to serve one already-configured SUMO command over stdio:

    python -m resto.interface.mcp.traci_server --net-file n.net.xml --route-files r.rou.xml
"""

from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

from resto.adapters.sumo import traci_api

_PRIMITIVES = (
    traci_api.close_lane,
    traci_api.open_lane,
    traci_api.set_speed,
    traci_api.set_tls_program,
    traci_api.get_edge_occupancy,
    traci_api.get_edge_speed,
    traci_api.get_vehicle_count,
    traci_api.step,
)


def build_server(name: str = "TraciMCP") -> MCPServer:
    server = MCPServer(name)
    for fn in _PRIMITIVES:
        description = (fn.__doc__ or "").strip().splitlines()[0]
        server.add_tool(fn, name=fn.__name__, description=description)
    return server


def main() -> None:
    sumo_cmd = ["sumo", *sys.argv[1:]]
    traci_api.start(sumo_cmd)
    try:
        build_server().run()
    finally:
        traci_api.close()


if __name__ == "__main__":
    main()
