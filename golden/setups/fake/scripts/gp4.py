"""GP-4: forced-mode question, a plan that simulates only the base, one answer."""

from dataclasses import replace

from tests.unit.application._world import BASELINE_PLAN, DESCRIBE_CHANGE, answers

from golden.setups.fake.script import AgentScript
from resto.domain.value_objects.question import Mode

SCRIPT = AgentScript(
    question=replace(DESCRIBE_CHANGE, mode=Mode.FORCED),
    plans=(BASELINE_PLAN,),
    expert=(answers(),),
)
