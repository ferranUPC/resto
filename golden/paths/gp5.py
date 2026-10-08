"""GP-5: a question whose two arms are stored costs no simulation.

The base and the treatment are stored before the request, so both experiments of the single phase
are reused. The steps are still traced: each build and run finds its result stored.
"""

from tests.unit.application._world import CLOSURE

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

GP5 = GoldenPath(
    name="gp5",
    request="What happens if lane 1 of E12 is closed?",
    prior=PriorState((StoredScenario(), StoredScenario((CLOSURE,)))),
    expected=ExpectedTrace(
        (
            ExpectedPhase(
                steps=steps(
                    "obtain_network",
                    "build_scenario",
                    "run_simulation",
                    "build_scenario",
                    "run_simulation",
                    "ask_expert",
                    "compose_report",
                ),
                arms=("base", "treatment"),
                reused=(True, True),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
                round=1,
            ),
        ),
        status=StudyStatus.COMPLETED,
    ),
)
