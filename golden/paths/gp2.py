"""GP-2: the baseline is built and run with the default seeds."""

from golden.framework import ExpectedPhase, ExpectedTrace, GoldenPath, steps
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.expert_answer import Basis

PATH = GoldenPath(
    name="gp2",
    request="how congested is the peak?",
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
                reused=(False,),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
                round=1,
            ),
        ),
        status=StudyStatus.COMPLETED,
    ),
)
