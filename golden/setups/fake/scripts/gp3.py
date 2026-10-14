"""GP-3: the plan covers both sides of the contrast in phase 0 (ADR-0038) and the Expert answers
with the treatment's mean delay."""

from tests.unit.application._world import WHAT_IF, WHAT_IF_PLAN, answers

from golden.setups.fake.script import AgentScript
from resto.domain.value_objects.answer_value import Measure, Quantity

SCRIPT = AgentScript(
    question=WHAT_IF,
    plans=(WHAT_IF_PLAN,),
    expert=(answers(Quantity(measure=Measure.MEAN_DELAY, value=31.0)),),
)
