"""GP-2: the baseline is built and run with the default seeds, and the Expert states how congested
the peak is.

Reference: ESTIMATE, not a measured value. No SUMO run backs it (the tests have no SUMO). The 24 s
is the mean delay of the baseline KPIs the shared test World stores (mean travel time 85 s against
61 s free flow), a fixture and not a simulation result. Regenerate it from a real SUMO run before
trusting it with a real setup (ADR-0043 section 3). 10 % tolerance: 21.6 to 26.4 s pass.
"""

from golden.framework import ExpectedAnswer, ExpectedKpi, ExpectedOutcome, GoldenPath
from resto.domain.value_objects.answer_value import Measure
from resto.domain.value_objects.expert_answer import Basis

PATH = GoldenPath(
    name="gp2",
    request="how congested is the peak?",
    expected=ExpectedOutcome(
        answer=ExpectedAnswer(
            kpis=(ExpectedKpi(Measure.MEAN_DELAY, reference=24.0, tolerance=0.10),),
            basis=Basis.OBSERVED,
            forced_by_limit=False,
        )
    ),
)
