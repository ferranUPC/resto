"""GP-4: forced mode. The Expert may not abstain, the plan still simulates only what it names.

Follows ADR-0038 section 4 and the glossary, not the frozen DoD row ("no simulation"): forced mode
only forbids abstaining. The base is simulated and the closure is not, so no stored simulation
matches the situation and the answer's `basis` is `extrapolated`; the limit did not force it.

Reference: ESTIMATE, not a measured value. No SUMO run backs it (the tests have no SUMO). It is
copied from the GP-3 estimate (about 30 s, 10 % tolerance: 27 to 33 s), itself a rough guess, and
here the Expert predicts it from the base without simulating the closure. Regenerate it from a real
SUMO run before trusting it with a real setup (ADR-0043 section 3).
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
