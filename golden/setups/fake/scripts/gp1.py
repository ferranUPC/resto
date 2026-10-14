"""GP-1: the Expert answers from a stored baseline."""

from tests.unit.application._world import BASELINE_PLAN, DESCRIBE, answers

from golden.setups.fake.script import AgentScript

SCRIPT = AgentScript(question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))
