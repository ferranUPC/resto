import pytest

from resto.domain.value_objects.outcomes import (
    AreaTooLarge,
    DemandNotNamed,
    DemandNotObtainable,
    FoundItem,
    NeedsUser,
    NetworkNotFound,
    SeveralCandidates,
    UnsupportedRequirement,
    WindowMissing,
)

REASONS = (
    WindowMissing(),
    DemandNotNamed(),
    DemandNotObtainable("Easter 2019"),
    NetworkNotFound("Gran Via"),
    SeveralCandidates(),
    AreaTooLarge(area_km2=101.0, limit_km2=10.0),
    UnsupportedRequirement("public transport stops"),
)


def test_area_too_large_names_both_areas_and_advises_a_smaller_one() -> None:
    reason = AreaTooLarge(area_km2=101.0, limit_km2=10.0)
    assert "smaller area" in reason.recommendation
    with pytest.raises(ValueError, match="limit_km2"):
        AreaTooLarge(area_km2=5.0, limit_km2=10.0)


def test_unsupported_requirement_names_what_is_missing() -> None:
    with pytest.raises(ValueError, match="requirement"):
        UnsupportedRequirement(" ")


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
