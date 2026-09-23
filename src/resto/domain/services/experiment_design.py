"""Which arms a question needs simulated (ADR-0027): the endpoints of its contrasts, nothing more.

Labels come back in a stable order — `BASE_ARM` first when needed, then the question's arms in the
order they were declared — so plans and gold plans compare without sorting.
"""

from __future__ import annotations

from collections.abc import Iterable

from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.question import Question


def required_arms(question: Question) -> tuple[str, ...]:
    """Every arm some contrast names, on either side. With no arms, only the base."""
    contrasts = question.effective_contrasts
    if not contrasts:
        return (BASE_ARM,)
    return _in_order(question, {label for c in contrasts for label in (c.treatment, c.reference)})


def reference_arms(question: Question) -> tuple[str, ...]:
    """The reference side of every contrast: what a `counterfactual` plans in phase 0 (ADR-0025 §2),
    leaving the treatments for the Expert to ask for."""
    contrasts = question.effective_contrasts
    if not contrasts:
        return (BASE_ARM,)
    return _in_order(question, {c.reference for c in contrasts})


def _in_order(question: Question, labels: Iterable[str]) -> tuple[str, ...]:
    wanted = set(labels)
    ordered = [BASE_ARM, *(a.label for a in question.effective_arms)]
    return tuple(label for label in ordered if label in wanted)
