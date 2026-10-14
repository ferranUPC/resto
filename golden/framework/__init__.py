"""Golden-path framework: the Expected outcome (ADR-0043) and its comparator, plus the Expected
trace beside it until r20 ticket 05 removes it.

The outcome is read from the finished study (`observe_outcome`) and compared with `compare_outcome`;
what follows describes the old trace.

A golden path says which trace a study must leave; a `Setup` runs it; `compare` checks what the
run left against what was expected, phase by phase.

Where each compared attribute is read from (confirmed in E9.1 slice 1):

- Events (`TraceEvent`): the (tool, status) sequence (`StepTraced`), the arms of the phase
  (`PlanMade.plan.arms`) and the round number (`ExpertRoundHeld.round`).
- The finished `Study`: `basis` (`phase.round.answer.basis`), `forced_by_limit`
  (`phase.round.forced_by_limit`) and `reused` (`phase.experiments[*].reused`). The events do not
  carry these three, so `observe` needs the `Study` next to the events; a `Setup` returns both.

Free text, tokens and ids are never compared: the observed side does not even hold them.
"""

from golden.framework.compare import Diff, Mismatch, compare, compare_outcome
from golden.framework.expected import (
    ExpectedPhase,
    ExpectedStep,
    ExpectedTrace,
    GoldenPath,
    PriorState,
    StoredScenario,
    steps,
)
from golden.framework.observed import ObservedPhase, observe
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

__all__ = [
    "Diff",
    "ExpectedAnswer",
    "ExpectedKpi",
    "ExpectedOutcome",
    "ExpectedPhase",
    "ExpectedResolution",
    "ExpectedStep",
    "ExpectedTrace",
    "GoldenPath",
    "Mismatch",
    "NetworkExpectation",
    "ObservedAnswer",
    "ObservedOutcome",
    "SameNetworkId",
    "Severity",
    "PriorState",
    "ObservedPhase",
    "Run",
    "Setup",
    "StoredScenario",
    "check",
    "compare",
    "compare_outcome",
    "observe",
    "observe_outcome",
    "steps",
]
