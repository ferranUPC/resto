"""What a specialist's `obtain_*` step ends in (ADR-0037 §3): the id of something already stored,
or a draft that code promotes (ADR-0001). The specialist never writes identity fields: `Found`
names an id the Executor checks against the repositories."""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.drafts import DemandDraft, NetworkDraft


@dataclass(frozen=True, slots=True)
class Found:
    """A stored network or demand that already answers the request."""

    id: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Found requires an id")


NetworkOutcome = Found | NetworkDraft
DemandOutcome = Found | DemandDraft
