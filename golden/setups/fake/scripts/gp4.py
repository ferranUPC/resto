"""GP-4: forced-mode question, a plan that simulates only the base, one answer that extrapolates
to the closure (no stored simulation matches it, ADR-0038 section 4)."""

from dataclasses import replace

from tests.unit.application._world import BASELINE_PLAN, DESCRIBE_CHANGE, answers

from golden.setups.fake.script import AgentScript
from resto.application.ports.llm import AgentRun
from resto.application.tools.expert import EvidenceLedger
from resto.domain.value_objects.answer_value import Measure, Quantity
from resto.domain.value_objects.expert_answer import Basis, ExpertAnswer
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask


def _extrapolated(task: ExpertTask, ledger: EvidenceLedger) -> AgentRun[ExpertAnswer]:
    run = answers(Quantity(measure=Measure.MEAN_DELAY, value=31.0))(task, ledger)
    assert run.output is not None
    return replace(run, output=replace(run.output, basis=Basis.EXTRAPOLATED))


SCRIPT = AgentScript(
    question=replace(DESCRIBE_CHANGE, mode=Mode.FORCED),
    plans=(BASELINE_PLAN,),
    expert=(_extrapolated,),
)
