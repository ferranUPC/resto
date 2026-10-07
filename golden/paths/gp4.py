"""GP-4: forced mode. The Expert may not abstain, the plan still simulates only what it names.

Follows ADR-0038 section 4 and the glossary, not the frozen DoD row ("no simulation"): forced
mode only forbids abstaining. The base is simulated; the treatment is predicted, so there is one
phase, only the base experiment, the answer's `basis` is set and no second phase follows.
"""

from golden.framework import ExpectedPhase, ExpectedTrace, GoldenPath, steps
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.expert_answer import Basis

GP4 = GoldenPath(
    name="gp4",
    request="Forced answer, no abstaining: how would closing lane 1 of E12 look?",
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
