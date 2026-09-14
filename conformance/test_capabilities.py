"""Contract §1/§8 item 3: capability derivation. A capability is present iff every tool listed
for it in §5 is present in `tools/list`; a partially implemented group (missing even one of its
tools) does not count as having that capability - the contract's own worked example is a server
exposing `store_note`/`search_notes` but not `update_note_status`, which must NOT count as having
`notes`.

Exercises `resto.application.capability_negotiation` (work-plan E1.6) - the Coordinator-facing
capability-listing helper - against a real server's `tools/list`, rather than duplicating the
derivation rule: this is the acceptance check any DatabaseMCP backend (including a third-party
one) must pass for that helper to negotiate it correctly at start-up."""

from __future__ import annotations

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.application.capability_negotiation import (
    CAPABILITY_TOOLS,
    REQUIRED_CAPABILITIES,
    capabilities_of,
)


def test_reference_server_exposes_every_required_capability(db: McpClientDatabase) -> None:
    assert capabilities_of(db.tool_names()) == REQUIRED_CAPABILITIES


def test_a_partially_implemented_group_does_not_count_as_a_capability() -> None:
    tool_names = _required_tool_names_missing("update_note_status")

    assert "notes" not in capabilities_of(tool_names)
    assert capabilities_of(tool_names) == REQUIRED_CAPABILITIES - {"notes"}


def _required_tool_names_missing(*excluded: str) -> frozenset[str]:
    required_tools = frozenset().union(*(CAPABILITY_TOOLS[c] for c in REQUIRED_CAPABILITIES))
    return required_tools - frozenset(excluded)


def test_an_unknown_extra_tool_does_not_change_capability_derivation(
    db: McpClientDatabase,
) -> None:
    tool_names = db.tool_names() | {"some_future_tool"}

    assert capabilities_of(tool_names) == REQUIRED_CAPABILITIES
