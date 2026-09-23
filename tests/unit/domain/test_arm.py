import pytest

from resto.domain.value_objects.arm import BASE_ARM, Arm, Contrast
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.question import SHORTHAND_ARM, Intent, Question
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import AddEdge, RemoveEdge, SetLanes

EVENING = TimeWindow(18 * 3600, 20 * 3600)
NEW_EDGE = AddEdge("J7", "J9", lanes=2, speed=13.9, edge_id="J7J9")


def _close_lane(edge_id: str, lane: int = 0) -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE, target=LaneTarget(edge_id, lane), window=EVENING
    )


def _retime_j4() -> Intervention:
    return Intervention(
        type=InterventionType.SIGNAL_PROGRAM,
        target=TlsTarget("J4"),
        params={"cycle": 90},
        window=EVENING,
    )


def _question(**kw):  # noqa: ANN003, ANN202
    return Question(text="what if…", intent=Intent.COMPARE, **kw)


# --- Arm ------------------------------------------------------------------------------------


def test_an_arm_changes_something_and_is_not_the_base() -> None:
    with pytest.raises(ValueError, match="base arm"):
        Arm("nothing")
    with pytest.raises(ValueError, match="implicit"):
        Arm(BASE_ARM, interventions=(_close_lane("E12"),))
    with pytest.raises(ValueError, match="label"):
        Arm(" ", interventions=(_close_lane("E12"),))


def test_an_intervention_can_target_an_edge_the_same_arm_adds() -> None:
    arm = Arm("edge+closure", topology_changes=(NEW_EDGE,), interventions=(_close_lane("J7J9"),))
    assert arm.topology_changes[0].edge_id == "J7J9"


def test_an_intervention_cannot_target_an_edge_the_arm_removes() -> None:
    with pytest.raises(ValueError, match="removed by this arm"):
        Arm(
            "x",
            topology_changes=(RemoveEdge("E12"),),
            interventions=(
                Intervention(
                    type=InterventionType.EDGE_CLOSURE, target=EdgeTarget("E12"), window=EVENING
                ),
            ),
        )


def test_an_intervention_cannot_target_a_lane_the_arm_leaves_out() -> None:
    with pytest.raises(ValueError, match="lanes"):
        Arm("x", topology_changes=(SetLanes("E12", 1),), interventions=(_close_lane("E12", 1),))
    Arm("x", topology_changes=(SetLanes("E12", 2),), interventions=(_close_lane("E12", 1),))


def test_added_edges_do_not_share_an_id() -> None:
    with pytest.raises(ValueError, match="edge_id"):
        Arm("x", topology_changes=(NEW_EDGE, AddEdge("J9", "J7", 1, 13.9, edge_id="J7J9")))
    with pytest.raises(ValueError, match="blank"):
        AddEdge("J7", "J9", 1, 13.9, edge_id=" ")


def test_a_contrast_compares_two_different_arms() -> None:
    assert Contrast("closure").reference == BASE_ARM
    with pytest.raises(ValueError, match="different"):
        Contrast("closure", "closure")


# --- Question -------------------------------------------------------------------------------


def test_arms_and_the_flat_shorthand_are_exclusive() -> None:
    with pytest.raises(ValueError, match="not both"):
        _question(
            interventions=(_close_lane("E12"),),
            arms=(Arm("retime", interventions=(_retime_j4(),)),),
        )


def test_contrasts_need_named_arms() -> None:
    with pytest.raises(ValueError, match="give the arms"):
        _question(interventions=(_close_lane("E12"),), contrasts=(Contrast(SHORTHAND_ARM),))
    arms = (Arm("closure", interventions=(_close_lane("E12"),)),)
    with pytest.raises(ValueError, match="unknown arm"):
        _question(arms=arms, contrasts=(Contrast("retime"),))


def test_arm_labels_and_contents_are_unique() -> None:
    closure = (_close_lane("E12"),)
    with pytest.raises(ValueError, match="unique"):
        _question(arms=(Arm("a", interventions=closure), Arm("a", interventions=(_retime_j4(),))))
    with pytest.raises(ValueError, match="same combination"):
        _question(arms=(Arm("a", interventions=closure), Arm("b", interventions=closure)))


def test_contrasts_do_not_repeat() -> None:
    arms = (Arm("closure", interventions=(_close_lane("E12"),)),)
    with pytest.raises(ValueError, match="repeat"):
        _question(arms=arms, contrasts=(Contrast("closure"), Contrast("closure")))


def test_the_shorthand_is_one_treatment_against_the_base() -> None:
    q = _question(interventions=(_close_lane("E12"),), topology_changes=(NEW_EDGE,))
    (arm,) = q.effective_arms
    assert arm == Arm(SHORTHAND_ARM, (NEW_EDGE,), (_close_lane("E12"),))
    assert q.effective_contrasts == (Contrast(SHORTHAND_ARM, BASE_ARM),)


def test_a_question_without_anything_to_simulate_has_no_arms() -> None:
    q = _question()
    assert q.effective_arms == ()
    assert q.effective_contrasts == ()


def test_arms_without_contrasts_are_each_compared_with_the_base() -> None:
    arms = (
        Arm("closure", interventions=(_close_lane("E12"),)),
        Arm("retime", interventions=(_retime_j4(),)),
    )
    assert _question(arms=arms).effective_contrasts == (Contrast("closure"), Contrast("retime"))
