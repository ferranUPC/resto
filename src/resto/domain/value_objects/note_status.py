"""Whether a later `SimulationResult` confirmed or refuted an `ExpertNote` (ADR-0011).

Defined apart from `ExpertNote` so `resto.domain.events` can carry it without importing the entity
that returns those events. `resto.domain.entities.expert_note` re-exports it.
"""

from __future__ import annotations

from enum import StrEnum


class NoteStatus(StrEnum):
    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
