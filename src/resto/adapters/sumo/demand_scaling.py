"""`DemandScaler` for the `demand_scale` mechanism (work-plan E2.3; architecture §2.2:
"`demand_scale` produces a derived demand with `scale` in its spec").

Deterministic by construction rather than by seeding an RNG: each original `<trip>` is kept,
dropped or duplicated by an error-diffusion rule (`round(i * factor) - round((i - 1) * factor)`
extra copies at index `i`), so the emitted count is `round(n * factor)` exactly and departures
stay proportionally spread rather than clumped — no randomness needed, so re-running the same
scale on the same trips file byte-identically reproduces the output. Routing the result (a new
`DemandTools.duarouter` call) is a separate step: this only touches the trips file.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.domain.value_objects.artifact_ref import ArtifactRef

OUTPUT_NAME = "scaled.trips.xml"


def _render(root: ET.Element) -> str:
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode") + "\n"


class SumoDemandScaler:
    """`DemandScaler` port: resamples a `<trip>`-only trips file (E0.6's `randomTrips.py
    --output-trip-file` shape) by a multiplicative `factor`."""

    def scale(self, trips: ArtifactRef, factor: float, out_dir: Path) -> ArtifactRef:
        """Writes `<out_dir>/scaled.trips.xml`.

        Raises:
            ValueError: `factor` is not positive.
        """
        if factor <= 0:
            raise ValueError("factor must be positive")

        source = ET.parse(trips.path)
        original_trips = source.getroot().findall("trip")

        root = ET.Element("routes")
        emitted_before = 0
        for i, trip in enumerate(original_trips, start=1):
            emitted_after = round(i * factor)
            for k in range(emitted_after - emitted_before):
                copy = ET.SubElement(root, "trip", trip.attrib)
                if k > 0:
                    copy.set("id", f"{trip.get('id')}_x{k}")
            emitted_before = emitted_after

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / OUTPUT_NAME
        path.write_text(_render(root), encoding="utf-8")
        return artifact_ref(path, "trips")
