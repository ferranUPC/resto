"""GP-5: a contrast whose two arms are stored; the plan names both, the Expert answers once."""

from tests.unit.application._world import WHAT_IF, WHAT_IF_PLAN, answers

from golden.setups.fake.script import AgentScript

SCRIPT = AgentScript(question=WHAT_IF, plans=(WHAT_IF_PLAN,), expert=(answers(),))
