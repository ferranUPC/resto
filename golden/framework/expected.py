"""A golden path: a request, the world it starts from and its Expected outcome. Data only, never
agent output."""

from __future__ import annotations

from dataclasses import dataclass

from golden.framework.outcome import ExpectedOutcome
from resto.domain.constants import DEFAULT_SEEDS
from resto.domain.value_objects.intervention import Intervention


@dataclass(frozen=True, slots=True)
class StoredScenario:
    """A scenario of the study network already stored, with ok results for `seeds`."""

    interventions: tuple[Intervention, ...] = ()
    seeds: tuple[int, ...] = DEFAULT_SEEDS


@dataclass(frozen=True, slots=True)
class PriorState:
    """What the world holds before the request. Stored facts only, never agent output, so every
    setup can start from it."""

    stored: tuple[StoredScenario, ...] = ()


@dataclass(frozen=True, slots=True)
class GoldenPath:
    """A request, the world it starts from and the outcome a correct study leaves."""

    name: str
    request: str
    expected: ExpectedOutcome
    prior: PriorState = PriorState()
