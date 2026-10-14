"""GP-5: a question whose two arms are stored costs no simulation.

The base and the treatment are stored before the request, so both essential simulations are
reused and the bound of new simulations is zero.
"""

from tests.unit.application._world import CLOSURE

from golden.framework import (
    EssentialSimulation,
    ExpectedOutcome,
    ExpectedResolution,
    GoldenPath,
    InterventionPredicate,
    PriorState,
    SimulationsExpectation,
    StoredScenario,
)
from resto.domain.entities.study import StudyResolution

GP5 = GoldenPath(
    name="gp5",
    request="What happens if lane 1 of E12 is closed?",
    prior=PriorState((StoredScenario(), StoredScenario((CLOSURE,)))),
    expected=ExpectedOutcome(
        resolution=ExpectedResolution(StudyResolution.COMPLETED),
        simulations=SimulationsExpectation(
            (
                EssentialSimulation(),
                EssentialSimulation((InterventionPredicate(CLOSURE.type, CLOSURE.target),)),
            ),
            max_new=0,
        ),
    ),
)
