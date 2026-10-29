"""Manual run of the OpenStreetMap import (E6.1), without any model: zero LLM cost.

Nominatim, Overpass and `netconvert` are real, so the run needs internet. Not a pytest test.
Snapshots and geocoder answers are cached under `--work`, so a second run of the same area
does not call the public services again.

    python scripts/manual_network_import_run.py --place "Adlershof, Berlin" --work DIR
    python scripts/manual_network_import_run.py --bbox 52.425 13.52 52.439 13.545 --work DIR --gui

`--bbox` is south west north east, in degrees. `--gui` opens the result in `sumo-gui`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from xml.etree import ElementTree

from resto.adapters.osm.nominatim import NominatimGeocoder
from resto.adapters.osm.overpass import OverpassOsmSource
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.osm_import import (
    PROFILES,
    Cleanups,
    netconvert_options,
    profile_named,
    resolve_area,
)
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.domain.services.content_hash import short_hash
from resto.domain.services.geo import area_km2
from resto.domain.value_objects.network_source import BBox, PlaceName
from resto.domain.value_objects.outcomes import NeedsUser


def _edges(net_xml: Path) -> int:
    return sum(
        1
        for _, element in ElementTree.iterparse(net_xml)
        if element.tag == "edge" and element.get("function") != "internal"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--place", help="administrative area, e.g. 'Adlershof, Berlin'")
    where.add_argument("--bbox", type=float, nargs=4, metavar=("S", "W", "N", "E"))
    ap.add_argument("--profile", default="roads", choices=[p.name for p in PROFILES])
    ap.add_argument("--remove-isolated", action="store_true")
    ap.add_argument("--join-junctions", action="store_true")
    ap.add_argument("--vclass", help="keep only edges that allow this vehicle class")
    ap.add_argument("--work", type=Path, required=True, help="directory for caches and results")
    ap.add_argument("--gui", action="store_true", help="open the network in sumo-gui")
    args = ap.parse_args()

    limits = OsmLimits()
    geocoder = NominatimGeocoder(args.work / "geocoder")
    source = OverpassOsmSource(limits=limits)
    runner = SubprocessNetconvertRunner()

    request = PlaceName(args.place) if args.place else BBox(*args.bbox)
    print(f"request: {request}")
    try:
        area = resolve_area(request, (), geocoder, limits)
        if isinstance(area, NeedsUser):
            print(f"needs the user: {area.message}")
            return 1
        print(f"area: {area_km2(area):.2f} km2 (limit {limits.max_area_km2:g} km2)")
        started = time.monotonic()
        snapshot = source.fetch(area, args.work / "osm")
        print(
            f"snapshot: {snapshot.path} ({snapshot.path.stat().st_size / 1e6:.1f} MB, "
            f"{time.monotonic() - started:.0f} s)"
        )
    except ExternalServiceError as error:
        print(f"service failed: {error}")
        return 2

    cleanups = Cleanups(
        remove_isolated=args.remove_isolated,
        join_junctions=args.join_junctions,
        vclass=args.vclass,
    )
    options = netconvert_options(profile_named(args.profile), area, typemap_dir(), cleanups)
    print("netconvert options:", " ".join(options))
    net = runner.build(
        snapshot, None, options, args.work / "imported" / short_hash(snapshot.content_hash)
    )
    edges = _edges(net.path)
    print(f"network: {net.path}")
    print(f"edges: {edges} (limit {limits.max_edges})  hash {net.content_hash}")
    if edges > limits.max_edges:
        print("above the edge limit: the Network Author would answer NeedsUser")

    if args.gui:
        import subprocess

        subprocess.run(["sumo-gui", "-n", str(net.path)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
