from __future__ import annotations

from dataclasses import replace

from golden.framework import GoldenPath, Run, check
from golden.paths.gp9 import GP9
from golden.setups.fake import FakeSetup, scripts
from golden.setups.fake.scripts.gp9 import SCRIPT

from resto.application.ports.tracing import PlanMade
from resto.domain.entities.study import StudyStatus
from tests.unit.application._world import BASELINE_PLAN, DESCRIBE, answers


def test_gp9_passes_against_the_fake() -> None:
    setup = FakeSetup()

    assert check(setup, GP9).ok
    assert setup.run(GP9).study.status is StudyStatus.AWAITING_USER


def test_the_script_flags_the_request_and_plans_nothing() -> None:
    assert "gp9" in scripts.discover()
    assert SCRIPT.question is not None and SCRIPT.question.ambiguities
    assert SCRIPT.plans == () and SCRIPT.expert == ()


def test_a_parser_that_does_not_flag_the_request_fails_gp9_with_a_diff() -> None:
    unflagged = FakeSetup(
        {"gp9": replace(SCRIPT, question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))}
    )

    diff = check(unflagged, GP9)

    assert not diff.ok
    assert "steps (tool, status): expected ()" in diff.render()


class _PlansAnyway:
    """The fake, plus a `PlanMade` the parser should never have let through."""

    repetitions = 1
    compare_repetitions = False

    def run(self, path: GoldenPath) -> Run:
        run = FakeSetup().run(path)
        return Run(run.study, (*run.events, PlanMade(0, BASELINE_PLAN)))


def test_a_parser_that_flags_the_request_but_still_plans_fails_gp9_naming_the_extra_events() -> (
    None
):
    text = check(_PlansAnyway(), GP9).render()

    assert "events: expected only" in text
    assert "PlanMade" in text
