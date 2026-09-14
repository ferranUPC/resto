"""Contract §1/§8 item 3: capability derivation. A capability is present iff every tool listed
for it in §5 is present in `tools/list`; a partially implemented group (missing even one of its
tools) does not count as having that capability - the contract's own worked example is a server
exposing `store_note`/`search_notes` but not `update_note_status`, which must NOT count as having
`notes`.

This mirrors the derivation rule verbatim; it does not reuse a shared implementation, because none
exists yet (work-plan E1.6 builds the Coordinator-facing capability-listing helper - this test is
what that helper will have to satisfy, not the helper itself)."""

from __future__ import annotations

from resto.adapters.persistence.mcp_client import McpClientDatabase

_CAPABILITY_GROUPS: dict[str, frozenset[str]] = {
    "networks": frozenset({"store_network", "get_network", "list_networks", "find_network"}),
    "demands": frozenset({"store_demand", "get_demand", "list_demands"}),
    "scenarios": frozenset({"store_scenario", "get_scenario", "find_similar_scenario"}),
    "results": frozenset({"store_result", "get_result", "list_results", "query_edgedata"}),
    "notes": frozenset({"store_note", "search_notes", "update_note_status"}),
}


def _capabilities(tool_names: frozenset[str]) -> frozenset[str]:
    return frozenset(
        group for group, required in _CAPABILITY_GROUPS.items() if required <= tool_names
    )


def test_reference_server_exposes_every_required_capability(db: McpClientDatabase) -> None:
    assert _capabilities(db.tool_names()) == frozenset(_CAPABILITY_GROUPS)


def test_a_partially_implemented_group_does_not_count_as_a_capability() -> None:
    tool_names = _tool_names_missing("update_note_status")

    assert "notes" not in _capabilities(tool_names)
    assert _capabilities(tool_names) == frozenset({"networks", "demands", "scenarios", "results"})


def _tool_names_missing(*excluded: str) -> frozenset[str]:
    all_tools = frozenset().union(*_CAPABILITY_GROUPS.values())
    return all_tools - frozenset(excluded)


def test_an_unknown_extra_tool_does_not_change_capability_derivation(
    db: McpClientDatabase,
) -> None:
    tool_names = db.tool_names() | {"some_future_tool"}

    assert _capabilities(tool_names) == frozenset(_CAPABILITY_GROUPS)
