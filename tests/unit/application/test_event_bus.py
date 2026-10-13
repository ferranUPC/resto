"""`EventBus` (ADR-0041 §11): synchronous, in order, a failing handler reported as telemetry, and a
fixed order for events a handler publishes while the bus is delivering."""

from __future__ import annotations

from resto.application.event_bus import EventBus
from resto.application.ports.tracing import HandlerFailed
from resto.domain.events import DomainEvent, NetworksAdded, PhaseStarted, ReportComposed
from tests.unit.application._world import RecordingTracer


class Recording:
    def __init__(self, name: str, log: list[tuple[str, str, DomainEvent]]) -> None:
        self._name = name
        self._log = log

    def __call__(self, study_id: str, event: DomainEvent) -> None:
        self._log.append((self._name, study_id, event))


def test_every_handler_gets_every_event_in_order_before_publish_returns() -> None:
    log: list[tuple[str, str, DomainEvent]] = []
    bus = EventBus(RecordingTracer())
    bus.subscribe("a", Recording("a", log))
    bus.subscribe("b", Recording("b", log))

    bus.publish("s1", (PhaseStarted(0), ReportComposed()))

    assert log == [
        ("a", "s1", PhaseStarted(0)),
        ("b", "s1", PhaseStarted(0)),
        ("a", "s1", ReportComposed()),
        ("b", "s1", ReportComposed()),
    ]


def test_a_failing_handler_is_traced_and_the_others_still_run() -> None:
    log: list[tuple[str, str, DomainEvent]] = []
    tracer = RecordingTracer()
    bus = EventBus(tracer)

    def boom(study_id: str, event: DomainEvent) -> None:
        raise RuntimeError("disk full")

    bus.subscribe("boom", boom)
    bus.subscribe("after", Recording("after", log))

    bus.publish("s1", (PhaseStarted(0), ReportComposed()))

    assert [e for _, _, e in log] == [PhaseStarted(0), ReportComposed()]
    assert tracer.events == [
        HandlerFailed("boom", "PhaseStarted", "RuntimeError: disk full"),
        HandlerFailed("boom", "ReportComposed", "RuntimeError: disk full"),
    ]


def test_an_event_published_by_a_handler_waits_until_the_current_events_are_delivered() -> None:
    """Queued, not delivered at once: the event that caused it and the events published with that
    one reach every handler first, whatever the order of subscription (ADR-0023: one replay)."""
    log: list[tuple[str, str, DomainEvent]] = []
    bus = EventBus(RecordingTracer())

    def reacting(study_id: str, event: DomainEvent) -> None:
        if isinstance(event, PhaseStarted):
            bus.publish(study_id, (NetworksAdded(("n1",)),))

    bus.subscribe("reacting", reacting)
    bus.subscribe("trace", Recording("trace", log))

    bus.publish("s1", (PhaseStarted(0), ReportComposed()))

    assert log == [
        ("trace", "s1", PhaseStarted(0)),
        ("trace", "s1", ReportComposed()),
        ("trace", "s1", NetworksAdded(("n1",))),
    ]
