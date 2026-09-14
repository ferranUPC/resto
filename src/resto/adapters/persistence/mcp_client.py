"""Repository adapters against an external DatabaseMCP server (E1.5).

Speaks real MCP over whatever transport it is handed (in-memory for tests, `stdio_client(...)`
for a subprocess, or any other `mcp.client` transport) via `mcp.client.session.ClientSession` -
this is the adapter the conformance suite (`conformance/`) runs through, so that "any
implementation" really means any server `build_server()` can front, not just the in-process
SQLite path in `persistence/sqlite/`.

The five per-aggregate classes below implement the exact same Protocols as
`persistence/sqlite/repositories.py` (`application/ports/repositories.py`), so callers - including
the conformance suite - can swap one backend for the other without changing a line of test/use
case code (architecture §2.4). `_store`/`_get`/`_list`/`_scored_pairs` factor out the repeated
dump/call/validate shape each method reduces to; the tool name and argument keys stay written out
per method (not derived from the aggregate name) so a tool rename or reshaped payload is still a
one-line diff, not a lookup through indirection.

Bridging sync and async: the repository ports are synchronous (same shape as the SQLite adapter),
but `ClientSession` is asyncio-native. anyio's cancel scopes (which the transport and the session
use internally) must be entered and exited from the *same asyncio Task* - scheduling `__aenter__`
and `__aexit__` as two separate `run_coroutine_threadsafe` calls, even onto the same loop, runs
them as two different Tasks and anyio rejects that ("Attempted to exit cancel scope in a different
task"). So the connection's whole lifetime - connect, every tool call, disconnect - runs inside
one long-lived coroutine (`_worker`, one Task) on a private background-thread event loop
(`_EventLoop`); the sync side talks to it through a request queue and blocks on a
`concurrent.futures.Future` per call.

Unwrapping: `mcp.server.mcpserver` represents a tool's structured output directly when its return
type is already a top-level JSON object (e.g. `store_*`'s `dict[str, str]`), and wraps anything
else - lists, `X | None`, arbitrary-keyed dicts stay ambiguous, per empirical check - in
`{"result": ...}` (see `database_server.py`'s own note on this). Rather than hardcode that per
tool, `_is_result_wrapper` checks each tool's published `output_schema` (cached at connect time)
for that wrapper shape (`properties == {"result": ...}` and `required == ["result"]`) generically.
A server that publishes no `output_schema` / `structuredContent` at all (a non-Python
implementation, say) is read from its first text content block as JSON instead, so the client
does not silently return `None` for every listing against such a backend.

Failure modes are errors, never hangs: a tool that does not answer within `timeout` raises
`TimeoutError`, and once the connection is gone (server crashed, transport closed, `close()`
called) every call - queued or new - fails with `ConnectionError` instead of blocking on a future
nobody will resolve.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.client.session import ClientSession

from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.schemas import ADAPTERS, adapter_for
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote, NoteStatus
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.value_objects.intervention import Intervention

TransportFactory = Callable[[], AbstractAsyncContextManager[tuple[Any, Any]]]

_ERROR_TYPES: dict[str, type[Exception]] = {
    "CONFLICT": ConflictError,
    "NOT_FOUND": NotFoundError,
    "INVALID_ARGUMENT": InvalidArgumentError,
}


def _raise_for_error_content(content: Sequence[Any]) -> None:
    text = content[0].text if content else "tool call failed with no error detail"
    for code, error_type in _ERROR_TYPES.items():
        marker = f"{code}: "
        index = text.find(marker)
        if index != -1:
            raise error_type(text[index + len(marker) :])
    raise RuntimeError(text)


def _parse_text_content(tool: str, content: Sequence[Any]) -> Any:
    """Fallback for servers that return no `structuredContent`: the first text block as JSON."""
    text = next((block.text for block in content if getattr(block, "text", None)), None)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"DatabaseMCP tool {tool!r} returned neither structuredContent nor a JSON text "
            f"block (got {text[:80]!r}); see DATABASE_MCP_CONTRACT.md §2 on result shape"
        ) from exc


def _is_result_wrapper(schema: Mapping[str, Any] | None) -> bool:
    if not schema:
        return False
    return set(schema.get("properties") or {}) == {"result"} and list(
        schema.get("required") or []
    ) == ["result"]


_STOP = object()


class _EventLoop:
    """A private asyncio event loop on a background thread, so a sync caller can drive an
    asyncio-native `ClientSession` without needing its own running loop."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    @property
    def stopped(self) -> bool:
        return self._loop.is_closed()

    def spawn(self, coro: Any) -> concurrent.futures.Future[Any]:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def submit_nowait(self, fn: Callable[..., None], *args: Any) -> None:
        self._loop.call_soon_threadsafe(fn, *args)

    def stop(self) -> None:
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
        self._loop.close()


class McpClientDatabase:
    """Connects to a DatabaseMCP server over `transport_factory` and exposes the same five
    repositories as `SqliteDatabase` (`.networks`, `.demands`, `.scenarios`, `.results`,
    `.notes`), backed by real MCP tool calls instead of direct SQL.

    Connect, every call, and disconnect all run inside one background Task (`_worker`, see the
    module docstring on why) - `_requests` is how the sync methods below hand it work.

    `timeout` bounds every single tool call (seconds; `None` waits forever). A call that times
    out is still in flight on the server - later calls queue behind it - so a timeout is a signal
    to give up on this connection, not to retry on it."""

    def __init__(self, transport_factory: TransportFactory, timeout: float | None = 30.0) -> None:
        self._timeout = timeout
        self._closed = False  # only ever touched on the event-loop thread (see `_enqueue`)
        self._worker_failure: BaseException | None = None
        self._events = _EventLoop()
        self._requests: asyncio.Queue[tuple[str, dict[str, Any], concurrent.futures.Future[Any]]]
        ready: concurrent.futures.Future[
            tuple[asyncio.Queue[Any], dict[str, Mapping[str, Any] | None]]
        ] = concurrent.futures.Future()
        self._worker_done = self._events.spawn(self._worker(transport_factory, ready))
        try:
            self._requests, self._output_schemas = ready.result()
        except BaseException:
            self._events.stop()
            raise

        self.networks: NetworkRepository = _NetworkRepository(self)
        self.demands: DemandRepository = _DemandRepository(self)
        self.scenarios: ScenarioRepository = _ScenarioRepository(self)
        self.results: ResultRepository = _ResultRepository(self)
        self.notes: NoteRepository = _NoteRepository(self)

    async def _worker(
        self,
        transport_factory: TransportFactory,
        ready: concurrent.futures.Future[Any],
    ) -> None:
        requests: asyncio.Queue[Any] = asyncio.Queue()
        try:
            async with transport_factory() as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                schemas = {tool.name: tool.output_schema for tool in listing.tools}
                ready.set_result((requests, schemas))

                while True:
                    item = await requests.get()
                    if item is _STOP:
                        break
                    name, arguments, future = item
                    try:
                        result = await session.call_tool(name, arguments)
                        future.set_result(result)
                    except Exception as exc:  # noqa: BLE001 - relayed to the caller's thread
                        future.set_exception(exc)
        except Exception as exc:  # noqa: BLE001 - relayed: to `ready` if connecting, else to callers
            if not ready.done():
                ready.set_exception(exc)
            else:
                self._worker_failure = exc
        finally:
            # Nothing will read `requests` again, whatever ended the connection: fail every
            # caller still queued instead of leaving it blocked on a future nobody resolves.
            self._closed = True
            while not requests.empty():
                item = requests.get_nowait()
                if item is not _STOP:
                    item[2].set_exception(self._connection_closed())

    def _connection_closed(self) -> ConnectionError:
        error = ConnectionError("DatabaseMCP connection is closed")
        error.__cause__ = self._worker_failure
        return error

    def _enqueue(self, item: Any) -> None:
        # Runs on the event-loop thread, like `_worker`'s `finally`, so `_closed` is checked and
        # set in one well-ordered place: no request can slip into the queue after the drain.
        if self._closed:
            if item is not _STOP:
                item[2].set_exception(self._connection_closed())
            return
        self._requests.put_nowait(item)

    def tool_names(self) -> frozenset[str]:
        return frozenset(self._output_schemas)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._events.stopped:
            raise self._connection_closed()
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        self._events.submit_nowait(self._enqueue, (name, arguments, future))
        try:
            result = future.result(timeout=self._timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"DatabaseMCP tool {name!r} did not answer within {self._timeout}s"
            ) from None
        if result.is_error:
            _raise_for_error_content(result.content)
        structured = result.structured_content
        if structured is None:
            structured = _parse_text_content(name, result.content)
        if _is_result_wrapper(self._output_schemas.get(name)):
            return structured["result"]
        return structured

    def close(self) -> None:
        """Disconnects and stops the background loop. Safe to call more than once."""
        if self._events.stopped:
            return
        self._events.submit_nowait(self._enqueue, _STOP)
        self._worker_done.result()
        self._events.stop()

    def __enter__(self) -> McpClientDatabase:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _store(db: McpClientDatabase, tool: str, payload_key: str, adapter: Any, entity: Any) -> None:
    db.call_tool(tool, {payload_key: adapter.dump_python(entity, mode="json")})


def _get(db: McpClientDatabase, tool: str, id_key: str, id_value: str, adapter: Any) -> Any:
    found = db.call_tool(tool, {id_key: id_value})
    return adapter.validate_python(found) if found is not None else None


def _list(db: McpClientDatabase, tool: str, arguments: dict[str, Any], adapter: Any) -> list[Any]:
    return [adapter.validate_python(item) for item in db.call_tool(tool, arguments)]


def _scored_pairs(
    found: list[dict[str, Any]], entity_key: str, adapter: Any
) -> list[tuple[Any, float]]:
    return [(adapter.validate_python(pair[entity_key]), pair["score"]) for pair in found]


class _NetworkRepository:
    def __init__(self, db: McpClientDatabase) -> None:
        self._db = db
        self._adapter = ADAPTERS["Network"]

    def store(self, network: Network) -> None:
        _store(self._db, "store_network", "network_data", self._adapter, network)

    def get(self, network_id: str) -> Network | None:
        return _get(self._db, "get_network", "network_id", network_id, self._adapter)

    def list(self) -> Sequence[Network]:
        return _list(self._db, "list_networks", {}, self._adapter)

    def find(
        self,
        source: str | None = None,
        derived_from: str | None = None,
        label: str | None = None,
    ) -> Sequence[Network]:
        args = {"source": source, "derived_from": derived_from, "label": label}
        return _list(self._db, "find_network", args, self._adapter)


class _DemandRepository:
    def __init__(self, db: McpClientDatabase) -> None:
        self._db = db
        self._adapter = ADAPTERS["Demand"]

    def store(self, demand: Demand) -> None:
        _store(self._db, "store_demand", "demand_data", self._adapter, demand)

    def get(self, demand_id: str) -> Demand | None:
        return _get(self._db, "get_demand", "demand_id", demand_id, self._adapter)

    def list(self, network_id: str) -> Sequence[Demand]:
        return _list(self._db, "list_demands", {"network_id": network_id}, self._adapter)


class _ScenarioRepository:
    def __init__(self, db: McpClientDatabase) -> None:
        self._db = db
        self._adapter = ADAPTERS["Scenario"]
        self._intervention_adapter = adapter_for(Intervention)

    def store(self, scenario: Scenario) -> None:
        _store(self._db, "store_scenario", "scenario_data", self._adapter, scenario)

    def get(self, scenario_id: str) -> Scenario | None:
        return _get(self._db, "get_scenario", "scenario_id", scenario_id, self._adapter)

    def find_similar(
        self,
        network_id: str,
        demand_id: str,
        interventions: Iterable[Intervention],
        context_tags: Iterable[str],
        limit: int = 10,
    ) -> Sequence[tuple[Scenario, float]]:
        found = self._db.call_tool(
            "find_similar_scenario",
            {
                "network_id": network_id,
                "demand_id": demand_id,
                "interventions": [
                    self._intervention_adapter.dump_python(i, mode="json") for i in interventions
                ],
                "context_tags": list(context_tags),
                "limit": limit,
            },
        )
        return _scored_pairs(found, "scenario", self._adapter)


class _ResultRepository:
    def __init__(self, db: McpClientDatabase) -> None:
        self._db = db
        self._adapter = ADAPTERS["SimulationResult"]

    def store(self, result: SimulationResult) -> None:
        _store(self._db, "store_result", "result_data", self._adapter, result)

    def get(self, result_id: str) -> SimulationResult | None:
        return _get(self._db, "get_result", "result_id", result_id, self._adapter)

    def list(self, scenario_id: str) -> Sequence[SimulationResult]:
        return _list(self._db, "list_results", {"scenario_id": scenario_id}, self._adapter)

    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]:
        return self._db.call_tool(
            "query_edgedata",
            {"result_id": result_id, "edge_ids": list(edge_ids), "window": window},
        )


class _NoteRepository:
    def __init__(self, db: McpClientDatabase) -> None:
        self._db = db
        self._adapter = ADAPTERS["ExpertNote"]

    def store(self, note: ExpertNote) -> None:
        _store(self._db, "store_note", "note_data", self._adapter, note)

    def search(
        self,
        query: str,
        network_id: str,
        filters: Mapping[str, Any],
        limit: int = 10,
    ) -> Sequence[tuple[ExpertNote, float]]:
        found = self._db.call_tool(
            "search_notes",
            {"query": query, "network_id": network_id, "filters": dict(filters), "limit": limit},
        )
        return _scored_pairs(found, "note", self._adapter)

    def update_status(self, note_id: str, status: NoteStatus) -> None:
        self._db.call_tool("update_note_status", {"note_id": note_id, "status": status.value})
