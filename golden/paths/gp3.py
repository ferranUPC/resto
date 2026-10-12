"""GP-3: a question that names a change, and the Expert asking for an arm the plan did not need.

`PATH` is GP-3 as the DoD states it: phase 0 plans only the base, the Expert answers free, with no
match and `needs_simulation`, and phase 1 realises the treatment. Two phases, arms by phase.
`SINGLE_PHASE` is the variant where the plan covers both sides in phase 0 (ADR-0038).
"""

from golden.framework import ExpectedPhase, ExpectedTrace, GoldenPath, steps
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.expert_answer import Basis

_BUILD_AND_RUN = ("obtain_network", "build_scenario", "run_simulation")


PATH = GoldenPath(
    name="gp3",
    request="how would closing lane 1 of E12 look?",
    expected=ExpectedTrace(
        (
            ExpectedPhase(
                steps=steps(*_BUILD_AND_RUN, "ask_expert"),
                arms=("base",),
                reused=(False,),
                basis=Basis.INFERRED,
                forced_by_limit=False,
                round=1,
            ),
            ExpectedPhase(
                steps=steps(*_BUILD_AND_RUN, "ask_expert", "compose_report"),
                arms=("treatment",),
                reused=(False,),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
                round=2,
            ),
        ),
        status=StudyStatus.COMPLETED,
    ),
)

SINGLE_PHASE = GoldenPath(
    name="gp3_single_phase",
    request="what if we close lane 1 of E12?",
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
                reused=(False, False),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
                round=1,
            ),
        ),
        status=StudyStatus.COMPLETED,
    ),
)
