"""Capability negotiation with DatabaseMCP at start-up (architecture §2.4; contract
DATABASE_MCP_CONTRACT.md §1; work-plan E1.6).

`capabilities_of` implements the contract's derivation rule verbatim: a capability group is
present iff every tool listed for it in contract §5 is present in the backend's `tools/list`
(mirrored here from `McpClientDatabase.tool_names()`, or any other tool-name set) - a partially
implemented group does not count (contract §5's own worked example: a server exposing
`store_note`/`search_notes` without `update_note_status` does not have `notes`).

`negotiate_capabilities` is what a Coordinator start-up sequence (E5, not yet built - see
`application/use_cases/run_study.py`) is meant to call once, right after connecting to a
DatabaseMCP backend: it hard-fails on a missing *required* capability (contract §1's negotiation
table - "the framework does not start in a degraded mode for required capabilities") and
otherwise reports whether the optional `historical_demand` capability is available, for the
Demand Generator's parameter-driven fallback to act on (contract §1, golden path GP-10).

`conformance/test_capabilities.py` imports `CAPABILITY_TOOLS`/`REQUIRED_CAPABILITIES`/
`capabilities_of` from here too, so the frozen contract table has exactly one source of truth
instead of being duplicated between the helper and its acceptance test.
"""

from __future__ import annotations

from dataclasses import dataclass

CAPABILITY_TOOLS: dict[str, frozenset[str]] = {
    "networks": frozenset({"store_network", "get_network", "list_networks", "find_network"}),
    "demands": frozenset({"store_demand", "get_demand", "list_demands"}),
    "scenarios": frozenset({"store_scenario", "get_scenario", "find_similar_scenario"}),
    "results": frozenset({"store_result", "get_result", "list_results", "query_edgedata"}),
    "notes": frozenset({"store_note", "search_notes", "update_note_status"}),
    "historical_demand": frozenset({"get_historical_demand"}),
}

REQUIRED_CAPABILITIES: frozenset[str] = frozenset(CAPABILITY_TOOLS) - {"historical_demand"}


class MissingRequiredCapabilityError(RuntimeError):
    """Raised by `negotiate_capabilities` when a DatabaseMCP backend lacks a required capability
    group. The framework does not start in a degraded mode for these (contract §1)."""


def capabilities_of(tool_names: frozenset[str]) -> frozenset[str]:
    """Every capability group whose tools are all present in `tool_names` (contract §1 rule)."""
    return frozenset(group for group, tools in CAPABILITY_TOOLS.items() if tools <= tool_names)


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """Result of a successful negotiation - every required capability was present."""

    available: frozenset[str]
    has_historical_demand: bool


def negotiate_capabilities(tool_names: frozenset[str]) -> CapabilityReport:
    """Derives capabilities from `tool_names` and hard-fails if any required one is missing.

    `tool_names` is the connected backend's advertised tool set, e.g.
    `McpClientDatabase.tool_names()` right after `session.initialize()`.

    Raises:
        MissingRequiredCapabilityError: names every missing required capability and, for each,
            the tools still needed - the message alone is actionable without re-deriving it.
    """
    available = capabilities_of(tool_names)
    missing = REQUIRED_CAPABILITIES - available
    if missing:
        detail = "; ".join(
            f"{group} (missing {sorted(CAPABILITY_TOOLS[group] - tool_names)})"
            for group in sorted(missing)
        )
        raise MissingRequiredCapabilityError(
            f"DatabaseMCP backend is missing required capabilities: {detail}"
        )
    return CapabilityReport(
        available=available, has_historical_demand="historical_demand" in available
    )
