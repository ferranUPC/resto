from resto.domain.services.experiment_design import reference_arms, required_arms
from resto.domain.value_objects.arm import BASE_ARM, Arm, Contrast
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget, TlsTarget
from resto.domain.value_objects.question import SHORTHAND_ARM, Intent, Question
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import AddEdge

EVENING = TimeWindow(18 * 3600, 20 * 3600)
NEW_EDGE = AddEdge("J7", "J9", lanes=2, speed=13.9, edge_id="J7J9")
CLOSURE = Intervention(
    type=InterventionType.LANE_CLOSURE, target=LaneTarget("gv_E12", 0), window=EVENING
)
RETIME = Intervention(
    type=InterventionType.SIGNAL_PROGRAM, target=TlsTarget("J4"), params={"c": 90}, window=EVENING
)


def _question(intent: Intent = Intent.COMPARE, **kw):  # noqa: ANN003, ANN202
    return Question(text="what if…", intent=intent, **kw)


def test_a_question_with_nothing_to_simulate_needs_the_base() -> None:
    q = _question(Intent.DESCRIBE)
    assert required_arms(q) == (BASE_ARM,)
    assert reference_arms(q) == (BASE_ARM,)


def test_the_shorthand_needs_base_and_treatment() -> None:
    q = _question(Intent.COUNTERFACTUAL, interventions=(CLOSURE,))
    assert required_arms(q) == (BASE_ARM, SHORTHAND_ARM)
    assert reference_arms(q) == (BASE_ARM,)


def test_only_the_combinations_the_contrasts_name_are_simulated() -> None:
    """Does the new edge compensate the closure, and is retiming J4 alone better than nothing?
    Two topology variants x three intervention sets would be 6 scenarios; the question needs 4,
    and only two of them (new-edge, new-edge+closure) need the derived network."""
    q = _question(
        arms=(
            Arm("new-edge", topology_changes=(NEW_EDGE,)),
            Arm("new-edge+closure", topology_changes=(NEW_EDGE,), interventions=(CLOSURE,)),
            Arm("retime", interventions=(RETIME,)),
            Arm("closure+retime", interventions=(CLOSURE, RETIME)),
        ),
        contrasts=(Contrast("new-edge+closure", "new-edge"), Contrast("retime")),
    )
    assert required_arms(q) == (BASE_ARM, "new-edge", "new-edge+closure", "retime")
    assert reference_arms(q) == (BASE_ARM, "new-edge")


def test_the_base_is_needed_only_when_a_contrast_names_it() -> None:
    q = _question(
        arms=(Arm("closure", interventions=(CLOSURE,)), Arm("retime", interventions=(RETIME,))),
        contrasts=(Contrast("closure", "retime"),),
    )
    assert required_arms(q) == ("closure", "retime")
    assert reference_arms(q) == ("retime",)
