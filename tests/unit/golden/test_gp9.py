from __future__ import annotations

from golden.framework import check
from golden.paths.gp9 import GP9
from golden.setups.fake import FakeSetup, scripts
from golden.setups.fake.scripts.gp9 import SCRIPT

from resto.domain.entities.study import StudyResolution


def test_gp9_passes_against_the_fake() -> None:
    setup = FakeSetup()

    assert check(setup, GP9).ok
    assert setup.run(GP9).study.resolution is StudyResolution.AWAITING_USER


def test_the_script_flags_the_request_and_plans_nothing() -> None:
    assert "gp9" in scripts.discover()
    assert SCRIPT.question is not None and SCRIPT.question.ambiguities
    assert SCRIPT.plans == () and SCRIPT.expert == ()
