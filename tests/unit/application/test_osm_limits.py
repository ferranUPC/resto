"""`OsmLimits`: the initial values of ADR-0045 §6 and their invariants."""

from __future__ import annotations

import pytest

from resto.application.ports.osm import OsmLimits


def test_the_defaults_are_the_initial_values_of_the_adr() -> None:
    limits = OsmLimits()

    assert limits.max_area_km2 == 25.0
    assert limits.max_edges == 25_000
    assert limits.overpass_maxsize_bytes == 256 * 1024 * 1024
    assert limits.overpass_timeout_s == 90


@pytest.mark.parametrize(
    "field", ["max_area_km2", "max_edges", "overpass_maxsize_bytes", "overpass_timeout_s"]
)
def test_a_limit_must_be_positive(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        OsmLimits(**{field: 0})
