from __future__ import annotations

from dataclasses import replace

import pytest
from golden.framework import (
    ExpectedPhase,
    ExpectedStep,
    ExpectedTrace,
    GoldenPath,
    PriorState,
    Run,
    StoredScenario,
    check,
    compare,
    observe,
)
from golden.setups.fake import AgentScript, FakeSetup, scripts

from resto.domain.value_objects.expert_answer import Basis
from tests.unit.application._world import BASELINE_PLAN, DESCRIBE, answers

TOOLS = (
    "obtain_network",
    "build_scenario",
    "run_simulation",
    "ask_expert",
    "compose_report",
)
SCRIPT = AgentScript(question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))
NO_PRIOR = PriorState()


def _path(
    name: str = "throwaway", *, prior: PriorState = NO_PRIOR, reused: bool = False
) -> GoldenPath:
    return GoldenPath(
        name=name,
        request="how congested is the peak?",
        expected=ExpectedTrace(
            (
                ExpectedPhase(
                    steps=tuple(ExpectedStep(t) for t in TOOLS),
                    arms=("base",),
                    reused=(reused,),
                    basis=Basis.OBSERVED,
                    forced_by_limit=False,
                    round=1,
                ),
            )
        ),
        prior=prior,
    )


def test_the_fake_repeats_three_times() -> None:
    assert FakeSetup({}).repetitions == 3


def test_a_throwaway_path_passes_the_comparator_through_the_fake() -> None:
    setup = FakeSetup({"throwaway": SCRIPT})

    run = setup.run(_path())

    assert compare(_path().expected, observe(run.study, run.events)).ok
    assert check(setup, _path()).ok


def test_the_prior_state_reaches_the_world() -> None:
    prior = PriorState((StoredScenario(),))
    setup = FakeSetup({"throwaway": SCRIPT})

    assert check(setup, _path(prior=prior, reused=True)).ok
    assert not check(setup, _path(prior=prior)).ok


def test_a_path_without_a_script_names_the_file_to_add() -> None:
    with pytest.raises(LookupError, match=r"scripts/missing\.py"):
        FakeSetup({}).run(_path("missing"))


def test_every_discovered_script_is_an_agent_script() -> None:
    assert all(isinstance(s, AgentScript) for s in scripts.discover().values())


class _Wobbly:
    """Wraps a setup; with `vary` the second repetition answers with another basis."""

    repetitions = 3

    def __init__(self, inner: FakeSetup, *, vary: bool) -> None:
        self._inner = inner
        self._vary = vary
        self._runs = 0

    def run(self, path: GoldenPath) -> Run:
        run = self._inner.run(path)
        self._runs += 1
        if not (self._vary and self._runs == 2):
            return run
        phase = run.study.phases[0]
        assert phase.round is not None
        answer = replace(phase.round.answer, basis=Basis.INFERRED)
        other = replace(phase, round=replace(phase.round, answer=answer))
        return Run(replace(run.study, phases=(other, *run.study.phases[1:])), run.events)


def test_repetitions_that_differ_fail_the_check() -> None:
    path = replace(
        _path(), expected=ExpectedTrace((replace(_path().expected.phases[0], basis=None),))
    )

    text = check(_Wobbly(FakeSetup({"throwaway": SCRIPT}), vary=True), path).render()

    assert "repetition 1" in text and "phase 0" in text


def test_repetitions_that_are_equal_pass_the_check() -> None:
    assert check(_Wobbly(FakeSetup({"throwaway": SCRIPT}), vary=False), _path()).ok
