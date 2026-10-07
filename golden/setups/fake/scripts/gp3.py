"""GP-3: the plan covers the base only; the Expert abstains and asks for the closure."""

from tests.unit.application._world import (
    BASELINE_PLAN,
    DESCRIBE_CHANGE,
    PROPOSED,
    TREATMENT_PLAN,
    abstains,
    answers,
)

from golden.setups.fake.script import AgentScript

SCRIPT = AgentScript(
    question=DESCRIBE_CHANGE,
    plans=(BASELINE_PLAN, TREATMENT_PLAN),
    expert=(abstains(PROPOSED), answers()),
)
