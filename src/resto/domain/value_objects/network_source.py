from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NetworkSourceKind = Literal["place", "bbox", "file"]


@dataclass(frozen=True, slots=True)
class NetworkSource:
    kind: NetworkSourceKind
    value: str
