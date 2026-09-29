"""Which artifacts define a reproducible run, and the hash over them.

`statistics` and `summary` carry wall-clock timings, so they are kept on a result but never hashed.
"""

from __future__ import annotations

from collections.abc import Iterable

from resto.domain.services.content_hash import compute_content_hash
from resto.domain.value_objects.artifact_ref import ArtifactRef

REPRODUCIBLE_KINDS = frozenset({"sumocfg", "additional", "edgedata", "tripinfo"})


def reproducibility_hash(artifacts: Iterable[ArtifactRef]) -> str:
    deterministic = sorted(
        (a.kind, a.content_hash) for a in artifacts if a.kind in REPRODUCIBLE_KINDS
    )
    return compute_content_hash("run", deterministic)
