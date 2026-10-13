"""Event handlers (ADR-0042 §11): what reacts to the domain events the event bus delivers.

A handler is an `EventHandler`. The bus calls it with the id of the study the event belongs to and
one event of a type it subscribed to, and queues the events the call returns
(`resto.application.event_bus`). A handler never holds a reference to the bus. A handler that
stores as it goes yields each event once its change is stored, so the events of the changes made
before a failure are still delivered.

- `trace.TraceHandler`: every domain event but `SimulationsRecorded` goes to the trace.
- `note_verification.NoteVerificationHandler`: the new results of a run step settle the unverified
  notes about their scenario.

The composition root (`interface/dependencies.py`) builds them and subscribes them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar

from resto.domain.events import DomainEvent

E_contra = TypeVar("E_contra", bound=DomainEvent, contravariant=True)


class EventHandler(Protocol[E_contra]):
    """Handles the events of the types it was subscribed to and returns the events it produced."""

    @property
    def name(self) -> str:
        """What `HandlerFailed` reports when the call raises."""
        ...

    def __call__(self, study_id: str, event: E_contra) -> Iterable[DomainEvent]: ...
