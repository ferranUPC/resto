import pytest

from resto.domain.value_objects.outcomes import (
    DemandNotNamed,
    DemandNotObtainable,
    FoundItem,
    NeedsUser,
    NetworkNotFound,
    SeveralCandidates,
    WindowMissing,
)

REASONS = (
    WindowMissing(),
    DemandNotNamed(),
    DemandNotObtainable("Easter 2019"),
    NetworkNotFound("Gran Via"),
    SeveralCandidates(),
)


def test_needs_user_requires_a_message() -> None:
    with pytest.raises(ValueError, match="message"):
        NeedsUser(WindowMissing(), "  ")


def test_several_candidates_needs_at_least_two() -> None:
    with pytest.raises(ValueError, match="two candidates"):
        NeedsUser(SeveralCandidates(), "which one?", ("bcn-1",))
    NeedsUser(SeveralCandidates(), "which one?", ("bcn-1", "bcn-2"))


@pytest.mark.parametrize("reason", REASONS)
def test_every_reason_has_a_default_recommendation(reason: object) -> None:
    candidates = ("a", "b") if isinstance(reason, SeveralCandidates) else ()
    needs = NeedsUser(reason, "what I was asked", candidates)  # type: ignore[arg-type]

    assert len(needs.recommendations) == 1 and needs.recommendations[0]


def test_the_specialists_advice_comes_after_the_default_recommendation() -> None:
    needs = NeedsUser(DemandNotNamed(), "no traffic named", advice=("try 'morning peak'",))

    assert needs.recommendations[1:] == ("try 'morning peak'",)


def test_a_found_item_requires_an_id() -> None:
    with pytest.raises(ValueError):
        FoundItem("network", "")
