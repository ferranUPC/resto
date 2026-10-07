"""GP-1: a stored baseline is answered from its results; nothing is built or simulated."""

from golden.framework import (
    ExpectedPhase,
    ExpectedTrace,
    GoldenPath,
    PriorState,
    StoredScenario,
    steps,
)
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.expert_answer import Basis

PATH = GoldenPath(
    name="gp1",
    request="how congested is the peak?",
    prior=PriorState(stored=(StoredScenario(),)),
    expected=ExpectedTrace(
        (
            ExpectedPhase(
                steps=steps(
                    "obtain_network",
                    "build_scenario",
                    "run_simulation",
                    "ask_expert",
                    "compose_report",
                ),
                arms=("base",),
                reused=(True,),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
                round=1,
            ),
        ),
        status=StudyStatus.COMPLETED,
    ),
)
