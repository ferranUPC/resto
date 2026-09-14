"""NetworkMCP server exposing the NetworkQuery port (DoD §4.9, work-plan E1.1).

Thin driving adapter (ADR-0009): all seven tools already exist as typed functions in
`application/tools/network.py`; this module only binds them to one loaded `.net.xml` and
registers them with the MCP server. No query logic lives here.

Run directly to serve one network over stdio:

    python -m resto.interface.mcp.network_server path/to/network.net.xml
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.network_query import NetworkQuery
from resto.application.tools.network import build_network_tools


def build_server(query: NetworkQuery, name: str = "NetworkMCP") -> MCPServer:
    server = MCPServer(name)
    for tool in build_network_tools(query):
        server.add_tool(tool.fn, name=tool.name, description=tool.description)
    return server


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: python -m {__name__} <net.xml>")
    query = SumolibNetworkQuery(Path(sys.argv[1]))
    build_server(query).run()


if __name__ == "__main__":
    main()
