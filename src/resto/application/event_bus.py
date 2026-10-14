"""The event bus (ADR-0041 §11, ADR-0042 §11): synchronous, in process, domain events only.

A use case stores what a transition returned, then publishes the transition's events under the id
of the study they belong to. `publish` returns once every handler got every event of the types it
subscribed to, in order of publication and, for one event, in order of subscription.

- **Handlers return events.** The events a handler returns are queued under the same study id and
  wait until the event being delivered and every event already queued reached every handler. The
  trace therefore reads the same whatever the order of subscription, and a study replays the same
  way every time (ADR-0023). No handler holds a reference to the bus.
- **A failing handler** never stops the others and never changes a study: the bus emits
  `HandlerFailed` to the `Tracer` port and goes on. The events it returned before it raised are
  still queued.

**Handler order.** The composition root (`interface/dependencies.py`) subscribes the trace first,
then note verification (`resto.application.event_handlers`). They share no event type today, so
the order only matters once a third handler shares one.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any, TypeVar

from resto.application.event_handlers import EventHandler
from resto.application.ports.tracing import HandlerFailed, Tracer
from resto.domain.events import DomainEvent

E = TypeVar("E", bound=DomainEvent)


class EventBus:
    def __init__(self, tracer: Tracer) -> None:
        """`tracer` receives the `HandlerFailed` telemetry."""
        self._tracer = tracer
        self._handlers: defaultdict[type, list[EventHandler[Any]]] = defaultdict(list)
        self._queue: deque[tuple[str, DomainEvent]] = deque()
        self._delivering = False

    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        """Adds `handler` after the handlers already subscribed to `event_type`."""
        self._handlers[event_type].append(handler)

    def publish(self, study_id: str, events: Iterable[DomainEvent]) -> None:
        """Delivers `events` of the study `study_id`, then the events the handlers return."""
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
        for handler in self._handlers[type(event)]:
            try:
                for produced in handler(study_id, event):
                    self._queue.append((study_id, produced))
            except Exception as e:
                failure = HandlerFailed(
                    handler.name, type(event).__name__, f"{type(e).__name__}: {e}"
                )
                self._tracer.emit(study_id, failure)
