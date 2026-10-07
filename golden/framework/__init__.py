"""Golden-path framework: the Expected trace, its projection from a run and the comparator.

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

from golden.framework.compare import Diff, Mismatch, compare
from golden.framework.expected import ExpectedPhase, ExpectedStep, ExpectedTrace, GoldenPath
from golden.framework.observed import ObservedPhase, observe
from golden.framework.setup import Run, Setup

__all__ = [
    "Diff",
    "ExpectedPhase",
    "ExpectedStep",
    "ExpectedTrace",
    "GoldenPath",
    "Mismatch",
    "ObservedPhase",
    "Run",
    "Setup",
    "compare",
    "observe",
]
