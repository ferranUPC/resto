"""GP-3, single-phase variant: the plan covers both sides of the contrast in phase 0."""

from tests.unit.application._world import WHAT_IF, WHAT_IF_PLAN, answers

from golden.setups.fake.script import AgentScript

SCRIPT = AgentScript(question=WHAT_IF, plans=(WHAT_IF_PLAN,), expert=(answers(),))
