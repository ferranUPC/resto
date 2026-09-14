"""DatabaseMCP server: the five required capability groups of DATABASE_MCP_CONTRACT.md over MCP,
wrapping one `SqliteDatabase` (E1.3). `historical_demand` is not implemented here - it is optional
(§1), and its shape is deliberately unpinned until E6.5 picks a data source (contract §10 point 3).

Thin driving adapter (ADR-0009): each tool function only (de)serialises through
`application.schemas.ADAPTERS` and calls straight into a `SqliteDatabase` repository - no logic
beyond that and error-code translation lives here.

Error codes (§7): this MCP SDK's tool-error model carries a message but no structured `code`
field, so every error this server raises is a `ToolError` whose message is prefixed with the
contract's stable code (`"CONFLICT: ..."`, `"NOT_FOUND: ..."`, `"INVALID_ARGUMENT: ..."`,
`"INTERNAL: ..."` for anything unexpected) - a client parses the code as the text before the
first `": "`. This is a pragmatic choice, not a contract requirement on transport shape; flagged
for review once the conformance suite (E1.5) needs to assert on codes programmatically.
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.application.schemas import ADAPTERS, adapter_for
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.value_objects.intervention import Intervention

_ERROR_CODES: tuple[tuple[type[Exception], str], ...] = (
    (ConflictError, "CONFLICT"),
    (NotFoundError, "NOT_FOUND"),
    (InvalidArgumentError, "INVALID_ARGUMENT"),
)


def _as_tool_error(exc: Exception) -> ToolError:
    for error_type, code in _ERROR_CODES:
        if isinstance(exc, error_type):
            return ToolError(f"{code}: {exc}")
    return ToolError(f"INTERNAL: {exc}")


def build_server(db: SqliteDatabase, name: str = "DatabaseMCP") -> MCPServer:
    server = MCPServer(name)
    network = ADAPTERS["Network"]
    demand = ADAPTERS["Demand"]
    scenario = ADAPTERS["Scenario"]
    result = ADAPTERS["SimulationResult"]
    note = ADAPTERS["ExpertNote"]
    intervention = adapter_for(Intervention)

    # --- networks ------------------------------------------------------------------------------

    def store_network(network_data: dict[str, Any]) -> dict[str, str]:
        parsed = network.validate_python(network_data)
        try:
            db.networks.store(parsed)
        except ConflictError as exc:
            raise _as_tool_error(exc) from exc
        return {"network_id": parsed.network_id}

    def get_network(network_id: str) -> dict[str, Any] | None:
        found = db.networks.get(network_id)
        return network.dump_python(found, mode="json") if found else None

    def list_networks() -> list[dict[str, Any]]:
        return [network.dump_python(n, mode="json") for n in db.networks.list()]

    def find_network(
        source: str | None = None,
        derived_from: str | None = None,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        found = db.networks.find(source=source, derived_from=derived_from, label=label)
        return [network.dump_python(n, mode="json") for n in found]

    # --- demands -------------------------------------------------------------------------------

    def store_demand(demand_data: dict[str, Any]) -> dict[str, str]:
        parsed = demand.validate_python(demand_data)
        try:
            db.demands.store(parsed)
        except ConflictError as exc:
            raise _as_tool_error(exc) from exc
        return {"demand_id": parsed.demand_id}

    def get_demand(demand_id: str) -> dict[str, Any] | None:
        found = db.demands.get(demand_id)
        return demand.dump_python(found, mode="json") if found else None

    def list_demands(network_id: str) -> list[dict[str, Any]]:
        return [demand.dump_python(d, mode="json") for d in db.demands.list(network_id)]

    # --- scenarios -------------------------------------------------------------------------------

    def store_scenario(scenario_data: dict[str, Any]) -> dict[str, str]:
        parsed = scenario.validate_python(scenario_data)
        try:
            db.scenarios.store(parsed)
        except ConflictError as exc:
            raise _as_tool_error(exc) from exc
        return {"scenario_id": parsed.scenario_id}

    def get_scenario(scenario_id: str) -> dict[str, Any] | None:
        found = db.scenarios.get(scenario_id)
        return scenario.dump_python(found, mode="json") if found else None

    def find_similar_scenario(
        network_id: str,
        demand_id: str,
        interventions: list[dict[str, Any]],
        context_tags: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        parsed_interventions = [intervention.validate_python(i) for i in interventions]
        pairs = db.scenarios.find_similar(
            network_id, demand_id, parsed_interventions, context_tags, limit
        )
        return [
            {"scenario": scenario.dump_python(s, mode="json"), "score": score}
            for s, score in pairs
        ]

    # --- results ---------------------------------------------------------------------------------

    def store_result(result_data: dict[str, Any]) -> dict[str, str]:
        parsed = result.validate_python(result_data)
        try:
            db.results.store(parsed)
        except ConflictError as exc:
            raise _as_tool_error(exc) from exc
        return {"result_id": parsed.result_id}

    def get_result(result_id: str) -> dict[str, Any] | None:
        found = db.results.get(result_id)
        return result.dump_python(found, mode="json") if found else None

    def list_results(scenario_id: str) -> list[dict[str, Any]]:
        return [result.dump_python(r, mode="json") for r in db.results.list(scenario_id)]

    def query_edgedata(
        result_id: str, edge_ids: list[str], window: tuple[float, float] | None = None
    ) -> dict[str, dict[str, float]]:
        try:
            return dict(db.results.query_edgedata(result_id, edge_ids, window))
        except NotFoundError as exc:
            raise _as_tool_error(exc) from exc

    # --- notes -----------------------------------------------------------------------------------

    def store_note(note_data: dict[str, Any]) -> dict[str, str]:
        parsed = note.validate_python(note_data)
        try:
            db.notes.store(parsed)
        except ConflictError as exc:
            raise _as_tool_error(exc) from exc
        return {"note_id": parsed.note_id}

    def search_notes(
        query: str, network_id: str, filters: dict[str, Any] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        try:
            pairs = db.notes.search(query, network_id, filters or {}, limit)
        except InvalidArgumentError as exc:
            raise _as_tool_error(exc) from exc
        return [{"note": note.dump_python(n, mode="json"), "score": s} for n, s in pairs]

    def update_note_status(note_id: str, status: str) -> dict[str, str]:
        try:
            db.notes.update_status(note_id, NoteStatus(status))
        except NotFoundError as exc:
            raise _as_tool_error(exc) from exc
        return {"note_id": note_id, "status": status}

    for fn, tool_name, description in (
        (store_network, "store_network", "Store a Network (idempotent on identical content)."),
        (get_network, "get_network", "Get a Network by id, or null if unknown."),
        (list_networks, "list_networks", "List every stored Network."),
        (find_network, "find_network", "Find Networks by source/derived_from/label (AND)."),
        (store_demand, "store_demand", "Store a Demand (idempotent on identical content)."),
        (get_demand, "get_demand", "Get a Demand by id, or null if unknown."),
        (list_demands, "list_demands", "List a network's Demands."),
        (store_scenario, "store_scenario", "Store a Scenario (idempotent on identical content)."),
        (get_scenario, "get_scenario", "Get a Scenario by id, or null if unknown."),
        (
            find_similar_scenario,
            "find_similar_scenario",
            "Exact-hash short-circuit, else rank Scenarios in a network by "
            "intervention/context_tags similarity.",
        ),
        (store_result, "store_result", "Store a SimulationResult (idempotent, same content)."),
        (get_result, "get_result", "Get a SimulationResult by id, or null if unknown."),
        (list_results, "list_results", "List a scenario's SimulationResults."),
        (query_edgedata, "query_edgedata", "Aggregate a result's edgedata over edges/window."),
        (store_note, "store_note", "Store an ExpertNote (idempotent on identical content)."),
        (search_notes, "search_notes", "Rank a network's ExpertNotes by similarity to a query."),
        (update_note_status, "update_note_status", "Update an ExpertNote's status."),
    ):
        server.add_tool(fn, name=tool_name, description=description)

    return server


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "resto.db"
    db = SqliteDatabase(db_path)
    try:
        build_server(db).run()
    finally:
        db.close()


if __name__ == "__main__":
    main()
