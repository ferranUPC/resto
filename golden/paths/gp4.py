"""GP-4: forced mode. The Expert may not abstain, the plan still simulates only what it names.

Follows ADR-0038 section 4 and the glossary, not the frozen DoD row ("no simulation"): forced mode
only forbids abstaining. The base is simulated and the closure is not, so no stored simulation
matches the situation and the answer's `basis` is `extrapolated`; the limit did not force it.

Reference (by hand; regenerate when a real SUMO run backs it, ADR-0043 section 3): the same as
GP-3, a mean delay of about 30 s with a 10 % tolerance (27 to 33 s), predicted from the base.
"""

from golden.framework import ExpectedAnswer, ExpectedKpi, ExpectedOutcome, GoldenPath
from resto.domain.value_objects.answer_value import Measure
from resto.domain.value_objects.expert_answer import Basis

GP4 = GoldenPath(
    name="gp4",
    request="Forced answer, no abstaining: how would closing lane 1 of E12 look?",
    expected=ExpectedOutcome(
        answer=ExpectedAnswer(
            kpis=(ExpectedKpi(Measure.MEAN_DELAY, reference=30.0, tolerance=0.10),),
            basis=Basis.EXTRAPOLATED,
            forced_by_limit=False,
        )
    ),
)
