"""The simulations part of the Expected outcome (ADR-0043 §3): which simulations a correct study had
to run and how many new ones it may run.

An essential simulation is a predicate on a scenario (the kind and target of its interventions, the
kind of its demand source, a range for numeric parameters), matched against the scenarios the study
ran and never against scenario ids. A reused result is not a new simulation; the same scenario id
with the same seeds twice in one study is redundant. The margin over the bound is zero unless the
golden path states a reason.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from golden.framework.outcome import Severity
from resto.domain.entities.demand import Demand
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.entities.study import Study
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import InterventionTarget


@dataclass(frozen=True, slots=True)
class ParamBound:
    """An intervention parameter must be a number in `[low, high]`, both ends included."""

    name: str
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(f"the range of {self.name!r} has its low end above its high end")

    def holds(self, params: Mapping[str, Any]) -> bool:
        value = params.get(self.name)
        return (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and self.low <= value <= self.high
        )

    def render(self) -> str:
        return f"{self.name} in [{self.low}, {self.high}]"


@dataclass(frozen=True, slots=True)
class InterventionPredicate:
    """The kind of an intervention, its target (`None`: any) and ranges for its parameters."""

    type: InterventionType
    target: InterventionTarget | None = None
    params: tuple[ParamBound, ...] = ()

    def matches(self, intervention: Intervention) -> bool:
        return (
            intervention.type is self.type
            and (self.target is None or self.target == intervention.target)
            and all(bound.holds(intervention.params) for bound in self.params)
        )

    def render(self) -> str:
        target = "" if self.target is None else f" on {self.target}"
        bounds = "".join(f" with {b.render()}" for b in self.params)
        return f"{self.type.value}{target}{bounds}"


@dataclass(frozen=True, slots=True)
class EssentialSimulation:
    """A scenario with exactly these interventions (none: the base), in order, over a demand with
    a source of `demand_source` kind (`None`: any)."""

    interventions: tuple[InterventionPredicate, ...] = ()
    demand_source: str | None = None

    def matches(self, simulation: ObservedSimulation) -> bool:
        return (
            len(self.interventions) == len(simulation.interventions)
            and all(
                p.matches(i)
                for p, i in zip(self.interventions, simulation.interventions, strict=True)
            )
            and (self.demand_source is None or self.demand_source in simulation.demand_sources)
        )

    def render(self) -> str:
        parts = " + ".join(p.render() for p in self.interventions) or "base"
        return parts if self.demand_source is None else f"{parts} over {self.demand_source} demand"


@dataclass(frozen=True, slots=True)
class SimulationsExpectation:
    """`max_new` new simulations are allowed, plus `margin` when the path states why."""

    essential: tuple[EssentialSimulation, ...]
    max_new: int
    margin: int = 0
    margin_reason: str | None = None
    severity: Severity = Severity.HARD

    def __post_init__(self) -> None:
        if self.max_new < 0 or self.margin < 0:
            raise ValueError("the bound and the margin of new simulations are >= 0")
        if self.margin > 0 and not (self.margin_reason or "").strip():
            raise ValueError("a margin over the essential simulations needs a stated reason")

    @property
    def allowed(self) -> int:
        return self.max_new + self.margin


@dataclass(frozen=True, slots=True)
class ObservedSimulation:
    """One scenario a study ran: its interventions, the kinds of its demand's sources, the seeds
    of its results and whether the results were reused."""

    scenario_id: str
    interventions: tuple[Intervention, ...]
    demand_sources: tuple[str, ...]
    seeds: tuple[int, ...]
    reused: bool


@dataclass(frozen=True, slots=True)
class Stored:
    """The stored facts a study's experiments point to; empty when a setup cannot read them."""

    scenarios: Mapping[str, Scenario]
    results: Mapping[str, SimulationResult]
    demands: Mapping[str, Demand]


NO_FACTS = Stored({}, {}, {})


def observe_simulations(study: Study, stored: Stored) -> tuple[ObservedSimulation, ...]:
    """Every experiment of the study, in phase order; one the facts do not hold is left out."""
    found: list[ObservedSimulation] = []
    for phase in study.phases:
        for experiment in phase.experiments:
            scenario = stored.scenarios.get(experiment.scenario_id)
            if scenario is None:
                continue
            demand = stored.demands.get(scenario.demand_id)
            kinds = tuple(s.kind for s in demand.sources) if demand else ()
            seeds = tuple(
                sorted(stored.results[r].seed for r in experiment.result_ids if r in stored.results)
            )
            found.append(
                ObservedSimulation(
                    experiment.scenario_id,
                    scenario.interventions,
                    kinds or ("parameters",),
                    seeds,
                    experiment.reused,
                )
            )
    return tuple(found)


def compare_simulations(
    expected: SimulationsExpectation, observed: Sequence[ObservedSimulation]
) -> list[tuple[str, object, object]]:
    """The mismatches as (what, expected, observed); empty when the part is met."""
    found: list[tuple[str, object, object]] = []
    free = list(observed)
    for essential in expected.essential:
        hit = next((s for s in free if essential.matches(s)), None)
        if hit is None:
            found.append(("simulations: essential simulation missing", essential.render(), "none"))
        else:
            free.remove(hit)
    new = sum(1 for s in observed if not s.reused)
    if new > expected.allowed:
        found.append(("simulations: new simulations", f"at most {expected.allowed}", new))
    twice = Counter((s.scenario_id, s.seeds) for s in observed)
    for (scenario_id, seeds), count in twice.items():
        if count > 1:
            found.append(
                (
                    "simulations: redundant simulation",
                    "once",
                    f"{scenario_id} with seeds {seeds} {count} times",
                )
            )
    return found
