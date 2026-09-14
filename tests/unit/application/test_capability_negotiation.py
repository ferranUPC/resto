"""Capability negotiation helper (work-plan E1.6, DATABASE_MCP_CONTRACT.md §1).

Pure logic over tool-name sets - no MCP session, no backend - so this is the exhaustive
case-by-case check of the derivation and negotiation rules; conformance/test_capabilities.py
exercises the same derivation against a real server's `tools/list`.
"""

from __future__ import annotations

import pytest

from resto.application.capability_negotiation import (
    CAPABILITY_TOOLS,
    REQUIRED_CAPABILITIES,
    CapabilityReport,
    MissingRequiredCapabilityError,
    capabilities_of,
    negotiate_capabilities,
)

_ALL_REQUIRED_TOOLS = frozenset().union(*(CAPABILITY_TOOLS[c] for c in REQUIRED_CAPABILITIES))


def test_required_capabilities_are_exactly_the_five_from_the_contract() -> None:
    assert frozenset(
        {"networks", "demands", "scenarios", "results", "notes"}
    ) == REQUIRED_CAPABILITIES


def test_capabilities_of_derives_a_group_only_when_every_one_of_its_tools_is_present() -> None:
    tool_names = _ALL_REQUIRED_TOOLS - {"update_note_status"}

    assert capabilities_of(tool_names) == REQUIRED_CAPABILITIES - {"notes"}


def test_capabilities_of_ignores_unknown_extra_tools() -> None:
    assert capabilities_of(_ALL_REQUIRED_TOOLS | {"some_future_tool"}) == REQUIRED_CAPABILITIES


def test_negotiate_succeeds_and_reports_no_historical_demand_when_only_required_present() -> None:
    report = negotiate_capabilities(_ALL_REQUIRED_TOOLS)

    assert report == CapabilityReport(available=REQUIRED_CAPABILITIES, has_historical_demand=False)


def test_negotiate_reports_historical_demand_when_its_tool_is_present() -> None:
    report = negotiate_capabilities(_ALL_REQUIRED_TOOLS | {"get_historical_demand"})

    assert report.has_historical_demand is True
    assert report.available == REQUIRED_CAPABILITIES | {"historical_demand"}


@pytest.mark.parametrize("missing_group", sorted(REQUIRED_CAPABILITIES))
def test_negotiate_hard_fails_naming_the_missing_capability_and_its_tools(
    missing_group: str,
) -> None:
    missing_tools = CAPABILITY_TOOLS[missing_group]
    tool_names = _ALL_REQUIRED_TOOLS - missing_tools

    with pytest.raises(MissingRequiredCapabilityError) as exc_info:
        negotiate_capabilities(tool_names)

    message = str(exc_info.value)
    assert missing_group in message
    for tool in missing_tools:
        assert tool in message


def test_negotiate_names_every_missing_required_capability_at_once() -> None:
    tool_names = CAPABILITY_TOOLS["networks"]  # only networks present

    with pytest.raises(MissingRequiredCapabilityError) as exc_info:
        negotiate_capabilities(tool_names)

    message = str(exc_info.value)
    for group in REQUIRED_CAPABILITIES - {"networks"}:
        assert group in message
