from __future__ import annotations

import pytest
from golden.framework import ExpectedOutcome, GoldenPath, check
from golden.paths import gp4, gp5
from golden.setups.fake import FakeSetup


@pytest.mark.parametrize("path", [gp4.GP4, gp5.GP5], ids=lambda p: p.name)
def test_the_path_passes_the_fake_with_an_empty_diff(path: GoldenPath) -> None:
    assert check(FakeSetup(), path).mismatches == ()


def test_gp5_has_both_arms_stored_and_allows_no_new_simulation() -> None:
    assert isinstance(gp5.GP5.expected, ExpectedOutcome)
    assert gp5.GP5.expected.simulations is not None
    assert gp5.GP5.expected.simulations.max_new == 0
    assert len(gp5.GP5.prior.stored) == 2
