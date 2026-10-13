"""`TraceHandler` (ADR-0041 §12, ADR-0042 §11), through the bus: every domain event but
`SimulationsRecorded` reaches the trace, under the study it was published for."""

from __future__ import annotations

from typing import cast, get_args

from resto.application.event_bus import EventBus
from resto.application.event_handlers.trace import TRACED_EVENTS, TraceHandler
from resto.application.ports.tracing import TraceEvent
from resto.domain.events import DomainEvent, SimulationsRecorded
from tests.unit.domain._samples import SAMPLES


class StudyTracer:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, TraceEvent]] = []

    def emit(self, study_id: str, event: TraceEvent) -> None:
        self.emitted.append((study_id, event))


def test_every_domain_event_but_simulations_recorded_is_traced() -> None:
    every = [cast(DomainEvent, SAMPLES[t]()) for t in get_args(DomainEvent)]
    tracer = StudyTracer()
    bus = EventBus(tracer)
    trace = TraceHandler(tracer)
    for event_type in TRACED_EVENTS:
        bus.subscribe(event_type, trace)

    bus.publish("s1", every)

    assert tracer.emitted == [("s1", e) for e in every if not isinstance(e, SimulationsRecorded)]
