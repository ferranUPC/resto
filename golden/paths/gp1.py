"""GP-1: a stored baseline is answered from its results; nothing is simulated."""

from golden.framework import (
    EssentialSimulation,
    ExpectedOutcome,
    ExpectedResolution,
    GoldenPath,
    PriorState,
    SimulationsExpectation,
    StoredScenario,
)
from resto.domain.entities.study import StudyResolution

PATH = GoldenPath(
    name="gp1",
    request="how congested is the peak?",
    prior=PriorState(stored=(StoredScenario(),)),
    expected=ExpectedOutcome(
        resolution=ExpectedResolution(StudyResolution.COMPLETED),
        simulations=SimulationsExpectation((EssentialSimulation(),), max_new=0),
    ),
)
