"""`DemandTools` adapter: `randomTrips`/`duarouter`/`routeSampler` wrappers (architecture §2.2).

`duarouter` is implemented now — work-plan E2.3 needs it to route a `demand_scale`-derived trips
file. `random_trips`/`route_sampler` are work-plan E6.2 (Demand Generator Minimal/Done): raising
`NotImplementedError` here rather than a bare placeholder keeps this adapter usable for the part
that already has a caller (ADR-0017's "raise, don't stub silently" convention — see
`SubprocessSumoRunner.run_online`).
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.domain.value_objects.artifact_ref import ArtifactRef

ROUTES_NAME = "routed.rou.xml"


class SumoDemandTools:
    """`DemandTools` port: shells out to the `duarouter`/`randomTrips.py`/`routeSampler.py`
    binaries on PATH (the pinned `eclipse-sumo` PyPI package, CLAUDE.md's SUMO_HOME convention)."""

    def __init__(self, duarouter_binary: str = "duarouter") -> None:
        self._duarouter = duarouter_binary

    def duarouter(
        self, net_xml: ArtifactRef, trips: ArtifactRef, seed: int, out_dir: Path
    ) -> ArtifactRef:
        """Routes `trips` over `net_xml`, writing `<out_dir>/routed.rou.xml`.

        Raises:
            RuntimeError: `duarouter` exits non-zero; the message is its own stderr.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / ROUTES_NAME
        proc = subprocess.run(
            [
                self._duarouter,
                "--net-file",
                str(net_xml.path),
                "--route-files",
                str(trips.path),
                "--output-file",
                str(out_path),
                "--seed",
                str(seed),
                "--ignore-errors",
                "false",
                "--no-step-log",
            ],
            capture_output=True,
            text=True,
            cwd=out_dir,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"duarouter failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return artifact_ref(out_path, "routes")

    def random_trips(
        self,
        net_xml: ArtifactRef,
        vph: float,
        window: tuple[float, float],
        seed: int,
        out_dir: Path,
    ) -> ArtifactRef:
        raise NotImplementedError("random_trips: see work-plan E6.2")

    def route_sampler(
        self,
        candidates: ArtifactRef,
        edgedata_counts: ArtifactRef,
        options: Sequence[str],
        seed: int,
        out_dir: Path,
    ) -> ArtifactRef:
        raise NotImplementedError("route_sampler: see work-plan E6.5")
