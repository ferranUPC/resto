"""GP-2: the baseline is built and run with the default seeds, and the Expert states how congested
the peak is.

Reference (by hand; regenerate when a real SUMO run backs it, ADR-0043 section 3): the peak of
the DEV-NET baseline has a mean delay of 24 s (mean travel time 85 s against 61 s free flow), taken
from the baseline KPIs the shared test World stores. 10 % tolerance: 21.6 to 26.4 s pass, 90 s or
10 s do not.
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
