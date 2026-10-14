"""GP-3 as the DoD states it: "What if I close lane 1 of E12?" (ADR-0038 section 3).

One phase plans both arms and the Expert answers on the contrast. The route is not asserted; the
outcome is the treatment's mean delay.

Reference: ESTIMATE, not a measured value. No SUMO run backs it (the tests have no SUMO). It is a
rough guess: closing one of the two lanes of E12 at the peak halves its capacity, so the network
mean delay was assumed to rise from the 24 s of the GP-2 estimate to about 30 s; it was not solved
by hand. Regenerate it from a real SUMO run before trusting it with a real setup (ADR-0043
section 3). 10 % tolerance: 27 to 33 s pass.
"""

from golden.framework import ExpectedAnswer, ExpectedKpi, ExpectedOutcome, GoldenPath
from resto.domain.value_objects.answer_value import Measure

PATH = GoldenPath(
    name="gp3",
    request="what if we close lane 1 of E12?",
    expected=ExpectedOutcome(
        answer=ExpectedAnswer(
            kpis=(ExpectedKpi(Measure.MEAN_DELAY, reference=30.0, tolerance=0.10),),
        )
    ),
)
