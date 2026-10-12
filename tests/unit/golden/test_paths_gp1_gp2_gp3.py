"""GP-1, GP-2 and GP-3 run through `check` with the fake setup: an empty diff."""

from __future__ import annotations

import pytest
from golden.framework import GoldenPath, check
from golden.paths import gp1, gp2, gp3
from golden.setups.fake import FakeSetup

PATHS = [gp1.PATH, gp2.PATH, gp3.PATH, gp3.SINGLE_PHASE]


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.name)
def test_the_fake_meets_the_expected_trace(path: GoldenPath) -> None:
    diff = check(FakeSetup(), path)

    assert diff.ok, diff.render()
