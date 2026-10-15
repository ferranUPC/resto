"""The Network Author's `probe_run` (ADR-0045): light random demand on a network, to see whether
it jams, teleports or collides. A probe is a check on a draft, not a result, so this port has no
repository and nothing it does reaches the results store."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.probe_report import ProbeReport


class NetworkProber(Protocol):
    def probe(
        self, net_xml: ArtifactRef, seed: int, vehicles: int, duration_s: float, out_dir: Path
    ) -> ProbeReport:
        """Everything the probe writes goes under `out_dir`.

        Raises:
            ValueError: no two edges of the network are joined by a route, so there is no demand.
            RuntimeError: SUMO could not run the probe; the message is SUMO's own.
        """
        ...
