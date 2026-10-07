"""GP-2: the baseline is built and run with the default seeds."""

from golden.framework import ExpectedPhase, ExpectedStep, ExpectedTrace, GoldenPath
from resto.domain.value_objects.expert_answer import Basis

PATH = GoldenPath(
    name="gp2",
    request="how congested is the peak?",
    expected=ExpectedTrace(
        (
            ExpectedPhase(
                steps=tuple(
                    ExpectedStep(tool)
                    for tool in (
                        "obtain_network",
                        "build_scenario",
                        "run_simulation",
                        "ask_expert",
                        "compose_report",
                    )
                ),
                arms=("base",),
                reused=(False,),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
                round=1,
            ),
        )
    ),
)
