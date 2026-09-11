from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NetworkSourceKind = Literal["place", "bbox", "file"]


@dataclass(frozen=True, slots=True)
class NetworkSource:
    kind: NetworkSourceKind
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("a NetworkSource requires a value")

    @property
    def needs_osm_snapshot(self) -> bool:
        return self.kind in ("place", "bbox")
