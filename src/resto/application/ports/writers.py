"""One deterministic writer per SUMO static mechanism; exposed to the Builder agent as tools."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.mechanism import StaticFileMechanism


class AdditionalFileWriter(Protocol):
    def supports(self, intervention: Intervention) -> bool: ...
    def write(self, intervention: Intervention, out_dir: Path) -> StaticFileMechanism: ...
