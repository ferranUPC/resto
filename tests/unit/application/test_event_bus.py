"""`EventBus` (ADR-0041 §11, ADR-0042 §11): synchronous, by event type, in order, a failing handler
reported as telemetry, and the events a handler returns queued behind the ones being delivered."""

from __future__ import annotations

from collections.abc import Iterator

from resto.application.event_bus import EventBus
from resto.application.ports.tracing import HandlerFailed
from resto.domain.events import DomainEvent, NetworksAdded, PhaseStarted, ReportComposed
from tests.unit.application._world import RecordingTracer

Log = list[tuple[str, str, DomainEvent]]


class Recording:
    def __init__(self, name: str, log: Log, *returns: DomainEvent) -> None:
        self.name = name
        self._log = log
        self._returns = returns

    def __call__(self, study_id: str, event: DomainEvent) -> tuple[DomainEvent, ...]:
        self._log.append((self.name, study_id, event))
        return self._returns


class Failing:
    name = "boom"

    def __call__(self, study_id: str, event: DomainEvent) -> tuple[DomainEvent, ...]:
        raise RuntimeError("disk full")


def test_a_handler_gets_only_the_event_types_it_subscribed_to() -> None:
    log: Log = []
    bus = EventBus(RecordingTracer())
    both = Recording("both", log)
    bus.subscribe(PhaseStarted, Recording("phases", log))
    bus.subscribe(PhaseStarted, both)
    bus.subscribe(ReportComposed, both)

    bus.publish("s1", (PhaseStarted(0), NetworksAdded(("n1",)), ReportComposed()))

    assert log == [
        ("phases", "s1", PhaseStarted(0)),
        ("both", "s1", PhaseStarted(0)),
        ("both", "s1", ReportComposed()),
    ]


def test_a_failing_handler_is_traced_and_the_others_still_run() -> None:
    log: Log = []
    tracer = RecordingTracer()
    bus = EventBus(tracer)
    failing, after = Failing(), Recording("after", log)
    types: tuple[type[DomainEvent], ...] = (PhaseStarted, ReportComposed)
    for event_type in types:
        bus.subscribe(event_type, failing)
        bus.subscribe(event_type, after)

    bus.publish("s1", (PhaseStarted(0), ReportComposed()))

    assert [e for _, _, e in log] == [PhaseStarted(0), ReportComposed()]
    assert tracer.events == [
        HandlerFailed("boom", "PhaseStarted", "RuntimeError: disk full"),
        HandlerFailed("boom", "ReportComposed", "RuntimeError: disk full"),
    ]


def test_the_events_a_handler_returns_wait_until_the_current_events_are_delivered() -> None:
    """Queued under the same study, not delivered at once: the event that caused them and the events
    published with that one reach every handler first, whatever the order of subscription
    (ADR-0023: one replay)."""
    log: Log = []
    bus = EventBus(RecordingTracer())
    bus.subscribe(PhaseStarted, Recording("reacting", [], NetworksAdded(("n1",))))
    trace = Recording("trace", log)
    types: tuple[type[DomainEvent], ...] = (PhaseStarted, ReportComposed, NetworksAdded)
    for event_type in types:
        bus.subscribe(event_type, trace)

    bus.publish("s1", (PhaseStarted(0), ReportComposed()))

    assert log == [
        ("trace", "s1", PhaseStarted(0)),
        ("trace", "s1", ReportComposed()),
        ("trace", "s1", NetworksAdded(("n1",))),
    ]


def test_a_handler_that_fails_midway_keeps_the_events_it_already_yielded() -> None:
    """A handler that stores as it goes yields each event once its change is stored, so a later
    failure does not hide a change that happened."""
    log: Log = []
    tracer = RecordingTracer()
    bus = EventBus(tracer)

    class Partial:
        name = "partial"

        def __call__(self, study_id: str, event: PhaseStarted) -> Iterator[DomainEvent]:
            yield NetworksAdded(("n1",))
            raise RuntimeError("disk full")

    bus.subscribe(PhaseStarted, Partial())
    bus.subscribe(NetworksAdded, Recording("trace", log))

    bus.publish("s1", (PhaseStarted(0),))

    assert log == [("trace", "s1", NetworksAdded(("n1",)))]
    assert tracer.events == [HandlerFailed("partial", "PhaseStarted", "RuntimeError: disk full")]
