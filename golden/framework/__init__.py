"""Golden-path framework: the Expected outcome (ADR-0043) and its comparator.

A golden path says what a correct study leaves: how it ends, which network it used, which
simulations it ran and how many new ones, and the KPIs the Expert gave, each with a relative
tolerance. Phases, step order and rounds are not part of it; the order of steps is held by the
`RunStudy` tests. A `Setup` runs a path and returns the finished `Study`, the tracer's events and
the stored facts; `observe_outcome` reads what the run left and `compare_outcome` checks it against
the expectation, part by part. A part the expectation leaves empty is not compared.

The observed side holds no free text, token counts or ids that are not part of an expectation:
KPIs are read from the typed values of the Expert's final answer, never from the prose.
"""

from golden.framework.compare import Diff, Mismatch, compare_outcome
from golden.framework.expected import (
    GoldenPath,
    PriorState,
    StoredScenario,
)
from golden.framework.outcome import (
    ExpectedAnswer,
    ExpectedKpi,
    ExpectedOutcome,
    ExpectedResolution,
    NetworkExpectation,
    ObservedAnswer,
    ObservedOutcome,
    SameNetworkId,
    Severity,
    observe_outcome,
)
from golden.framework.setup import Run, Setup, check
from golden.framework.simulations import (
    EssentialSimulation,
    InterventionPredicate,
    ObservedSimulation,
    ParamBound,
    SimulationsExpectation,
    Stored,
    observe_simulations,
)

__all__ = [
    "EssentialSimulation",
    "InterventionPredicate",
    "ObservedSimulation",
    "ParamBound",
    "SimulationsExpectation",
    "Stored",
    "observe_simulations",
    "Diff",
    "ExpectedAnswer",
    "ExpectedKpi",
    "ExpectedOutcome",
    "ExpectedResolution",
    "GoldenPath",
    "Mismatch",
    "NetworkExpectation",
    "ObservedAnswer",
    "ObservedOutcome",
    "SameNetworkId",
    "Severity",
    "PriorState",
    "Run",
    "Setup",
    "StoredScenario",
    "check",
    "compare_outcome",
    "observe_outcome",
]
