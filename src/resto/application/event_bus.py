"""The event bus (ADR-0041 §11): synchronous, in process, domain events only.

A use case stores what a transition returned, then publishes the transition's events under the id
of the study they belong to (the events carry none). `publish` returns once every handler got every
event, in order of publication and, for one event, in order of subscription.

- **A failing handler** never stops the others and never changes a study: the bus emits
  `HandlerFailed` to the `Tracer` port and goes on.
- **Nested publication is queued.** An event a handler publishes while the bus is delivering waits
  until the event being delivered and every event already queued reached every handler. The trace
  therefore reads the same whatever the order of subscription, and a study replays the same way
  every time (ADR-0023).

The subscribers are wired by the composition root (`interface/dependencies.py`).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable

from resto.application.ports.tracing import HandlerFailed, Tracer
from resto.domain.events import DomainEvent, SimulationsRecorded

Handler = Callable[[str, DomainEvent], None]
"""Takes the study id and one event; a handler ignores the event types it does not handle."""


class EventBus:
    def __init__(self, tracer: Tracer) -> None:
        """`tracer` receives the `HandlerFailed` telemetry."""
        self._tracer = tracer
        self._handlers: list[tuple[str, Handler]] = []
        self._queue: deque[tuple[str, DomainEvent]] = deque()
        self._delivering = False

    def subscribe(self, name: str, handler: Handler) -> None:
        """Adds `handler` after the ones already subscribed; `name` is what `HandlerFailed`
        reports."""
        self._handlers.append((name, handler))

    def publish(self, study_id: str, events: Iterable[DomainEvent]) -> None:
        """Delivers `events` of the study `study_id`; called from a handler, queues them."""
        self._queue.extend((study_id, event) for event in events)
        if self._delivering:
            return
        self._delivering = True
        try:
            while self._queue:
                self._deliver(*self._queue.popleft())
        finally:
            self._delivering = False
            self._queue.clear()

    def _deliver(self, study_id: str, event: DomainEvent) -> None:
        for name, handler in self._handlers:
            try:
                handler(study_id, event)
            except Exception as e:
                failure = HandlerFailed(name, type(event).__name__, f"{type(e).__name__}: {e}")
                self._tracer.emit(study_id, failure)


class TraceDomainEvents:
    """The trace subscriber: every domain event but `SimulationsRecorded` is a trace event."""

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer

    def __call__(self, study_id: str, event: DomainEvent) -> None:
        if isinstance(event, SimulationsRecorded):
            return  # note verification's, not traced
        self._tracer.emit(study_id, event)
