"""The options of an import that carry the area (ADR-0049)."""

from __future__ import annotations

from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.osm_import import Cleanups, netconvert_options, profile_named
from resto.domain.value_objects.network_source import Polygon


def test_a_seven_decimal_coordinate_reaches_the_netconvert_cut_intact() -> None:
    ring = ((41.3896127, 2.1494837), (41.3896127, 2.1605163), (41.3983873, 2.1605163))
    area = Polygon((*ring, ring[0]))

    options = netconvert_options(profile_named("roads"), area, typemap_dir(), Cleanups())

    boundary = options[options.index("--keep-edges.in-geo-boundary") + 1]
    assert boundary == (
        "2.1494837,41.3896127 2.1605163,41.3896127 2.1605163,41.3983873 2.1494837,41.3896127"
    )
