from __future__ import annotations

import pytest
from golden.framework import (
    ExpectedAnswer,
    ExpectedKpi,
    ExpectedOutcome,
    GoldenPath,
    PriorState,
    SimulationsExpectation,
    StoredScenario,
    check,
    compare_outcome,
    observe_outcome,
    observe_simulations,
)
from golden.setups.fake import AgentScript, FakeSetup, scripts

from resto.domain.value_objects.answer_value import Measure
from resto.domain.value_objects.expert_answer import Basis
from tests.unit.application._world import BASELINE_PLAN, DESCRIBE, answers

SCRIPT = AgentScript(question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))
NO_PRIOR = PriorState()


def _path(name: str = "throwaway", *, prior: PriorState = NO_PRIOR, max_new: int = 1) -> GoldenPath:
    return GoldenPath(
        name=name,
        request="how congested is the peak?",
        expected=ExpectedOutcome(
            simulations=SimulationsExpectation((), max_new=max_new),
            answer=ExpectedAnswer(
                kpis=(ExpectedKpi(Measure.MEAN_DELAY, reference=24.0, tolerance=0.10),),
                basis=Basis.OBSERVED,
                forced_by_limit=False,
            ),
        ),
        prior=prior,
    )


def test_the_fake_repeats_three_times() -> None:
    assert FakeSetup({}).repetitions == 3


def test_the_fake_compares_repetitions() -> None:
    assert FakeSetup({}).compare_repetitions is True


def test_a_throwaway_path_passes_the_comparator_through_the_fake() -> None:
    setup = FakeSetup({"throwaway": SCRIPT})

    run = setup.run(_path())
    observed = observe_outcome(run.study, observe_simulations(run.study, run.stored))

    assert compare_outcome(_path().expected, observed).ok
    assert check(setup, _path()).ok


def test_the_prior_state_reaches_the_world() -> None:
    prior = PriorState((StoredScenario(),))
    setup = FakeSetup({"throwaway": SCRIPT})

    assert check(setup, _path(prior=prior, max_new=0)).ok
    assert not check(setup, _path(max_new=0)).ok


def test_a_path_without_a_script_names_the_file_to_add() -> None:
    with pytest.raises(LookupError, match=r"scripts/missing\.py"):
        FakeSetup({}).run(_path("missing"))


def test_every_discovered_script_is_an_agent_script() -> None:
    assert all(isinstance(s, AgentScript) for s in scripts.discover().values())
