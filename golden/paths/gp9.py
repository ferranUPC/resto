"""GP-9: an ambiguous request awaits the user.

The request has two incompatible readings and names no network or demand. The study must end
`awaiting_user` and no simulation runs (a bound of zero new simulations). A setup whose parser
does not flag the request fails this path; that is a parser failure to show, not an exception.

A missing network or demand is not ambiguity (a failed step with a `StepError.kind`, E9.3), and a
specialist that asks the user mid-plan is a different flow.
"""

from golden.framework import (
    ExpectedOutcome,
    ExpectedResolution,
    GoldenPath,
    SimulationsExpectation,
)
from resto.domain.entities.study import StudyResolution

GP9 = GoldenPath(
    name="gp9",
    request="Make the morning peak better, either by cutting delays or by cutting emissions.",
    expected=ExpectedOutcome(
        resolution=ExpectedResolution(StudyResolution.AWAITING_USER),
        simulations=SimulationsExpectation((), max_new=0),
    ),
)
