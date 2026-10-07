"""GP-2: the baseline is built and run, then the Expert answers."""

from tests.unit.application._world import BASELINE_PLAN, DESCRIBE, answers

from golden.setups.fake.script import AgentScript

SCRIPT = AgentScript(question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))
