"""Which arms a question needs simulated (ADR-0027): the endpoints of its contrasts, nothing more.

Labels come back in a stable order — `BASE_ARM` first when needed, then the question's arms in the
order they were declared — so plans and gold plans compare without sorting.
"""

from __future__ import annotations

from collections.abc import Iterable

from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.time_window import TimeWindow


def required_arms(question: Question) -> tuple[str, ...]:
    """Every arm some contrast names, on either side. A `run` has no contrast to name arms, so it
    needs the arms it declares (ADR-0038). With no arms, only the base."""
    contrasts = question.effective_contrasts
    if not contrasts:
        arms = question.effective_arms
        if question.intent is Intent.RUN and arms:
            return tuple(a.label for a in arms)
        return (BASE_ARM,)
    return _in_order(question, {label for c in contrasts for label in (c.treatment, c.reference)})


def mode_for(question: Question, round_no: int, max_rounds: int) -> Mode:
    """Forced when the user asked for it, and always on round `max_rounds` (ADR-0025 §4)."""
    if question.mode is Mode.FORCED or round_no == max_rounds:
        return Mode.FORCED
    return Mode.FREE


def needed_arms(question: Question, phase: int) -> tuple[str, ...]:
    """The arms a phase must have realised (ADR-0038). `run` and `compare` need every arm the
    question needs from phase 0. `describe` and `diagnose` need only the base in phase 0, and every
    required arm from phase 1 on. A `network_only` question needs none: the plan stops at
    `obtain_network`."""
    if question.network_only:
        return ()
    if phase >= 1 or question.intent in (Intent.RUN, Intent.COMPARE):
        return required_arms(question)
    return (BASE_ARM,)


def study_window(question: Question) -> TimeWindow | None:
    """The smallest interval containing the window of every intervention in every arm, so all arms
    share one demand. Interventions with a `condition` have no window and add nothing. `None` when
    no intervention has a window: the Demand Generator then asks for the period."""
    interventions = [i for arm in question.effective_arms for i in arm.interventions]
    windows = [i.window for i in interventions if i.window is not None]
    if not windows:
        return None
    return TimeWindow(min(w.start for w in windows), max(w.end for w in windows))


def _in_order(question: Question, labels: Iterable[str]) -> tuple[str, ...]:
    wanted = set(labels)
    ordered = [BASE_ARM, *(a.label for a in question.effective_arms)]
    return tuple(label for label in ordered if label in wanted)
