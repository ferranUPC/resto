from dataclasses import replace

from resto.domain.services.experiment_design import (
    mode_for,
    needed_arms,
    required_arms,
    study_window,
)
from resto.domain.value_objects.arm import BASE_ARM, Arm, Contrast
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget, TlsTarget
from resto.domain.value_objects.question import SHORTHAND_ARM, Intent, Mode, Question
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


def test_the_shorthand_needs_base_and_treatment() -> None:
    q = _question(interventions=(CLOSURE,))
    assert required_arms(q) == (BASE_ARM, SHORTHAND_ARM)


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


def test_the_base_is_needed_only_when_a_contrast_names_it() -> None:
    q = _question(
        arms=(Arm("closure", interventions=(CLOSURE,)), Arm("retime", interventions=(RETIME,))),
        contrasts=(Contrast("closure", "retime"),),
    )
    assert required_arms(q) == ("closure", "retime")


def test_a_backwards_contrast_still_plans_the_contained_arm_as_the_reference() -> None:
    """ADR-0027 §1: "does the closure hurt on the network with the new edge?" written with the arms
    swapped still plans the new edge as the reference and the combination as the treatment."""
    q = _question(
        arms=(
            Arm("new-edge", topology_changes=(NEW_EDGE,)),
            Arm("new-edge+closure", topology_changes=(NEW_EDGE,), interventions=(CLOSURE,)),
        ),
        contrasts=(Contrast("new-edge", "new-edge+closure"),),
    )
    assert [(c.treatment, c.reference) for c in q.effective_contrasts] == [
        ("new-edge+closure", "new-edge")
    ]
    assert required_arms(q) == ("new-edge", "new-edge+closure")


def test_mode_for_forces_the_last_round_and_forced_questions() -> None:
    describe = _question(Intent.DESCRIBE)
    assert mode_for(describe, 1, 3) is Mode.FREE
    assert mode_for(describe, 3, 3) is Mode.FORCED
    assert mode_for(replace(describe, mode=Mode.FORCED), 1, 3) is Mode.FORCED


def test_a_network_only_question_needs_no_arm() -> None:
    question = Question(text="tell me about RIVERSIDE", intent=Intent.DESCRIBE, network_only=True)
    assert needed_arms(question, 0) == ()


def test_a_change_question_plans_both_sides_in_phase_0() -> None:
    """ADR-0038: the treatment is never held back for the Expert to request."""
    for intent in (Intent.COMPARE,):
        what_if = _question(intent, interventions=(CLOSURE,))
        assert needed_arms(what_if, 0) == (BASE_ARM, SHORTHAND_ARM)
        assert needed_arms(what_if, 1) == (BASE_ARM, SHORTHAND_ARM)


def test_describe_and_diagnose_plan_the_base_in_phase_0() -> None:
    for intent in (Intent.DESCRIBE, Intent.DIAGNOSE):
        assert needed_arms(_question(intent), 0) == (BASE_ARM,)
        with_change = _question(intent, interventions=(CLOSURE,))
        assert needed_arms(with_change, 0) == (BASE_ARM,)
        assert needed_arms(with_change, 1) == (BASE_ARM, SHORTHAND_ARM)


def test_a_run_has_no_default_contrast_so_it_plans_no_base() -> None:
    run = _question(Intent.RUN, interventions=(CLOSURE,))
    assert run.effective_contrasts == ()
    assert needed_arms(run, 0) == (SHORTHAND_ARM,)
    assert needed_arms(run, 1) == (SHORTHAND_ARM,)


def test_a_run_plans_the_declared_arms_only() -> None:
    run = _question(
        Intent.RUN,
        arms=(Arm("closure", interventions=(CLOSURE,)), Arm("retime", interventions=(RETIME,))),
    )
    assert needed_arms(run, 0) == ("closure", "retime")


def test_a_run_that_lists_the_base_as_an_arm_plans_it() -> None:
    run = _question(
        Intent.RUN,
        arms=(Arm("closure", interventions=(CLOSURE,)),),
        contrasts=(Contrast("closure"),),
    )
    assert needed_arms(run, 0) == (BASE_ARM, "closure")


def test_a_run_with_explicit_contrasts_plans_the_sides_they_declare() -> None:
    arms = (Arm("closure", interventions=(CLOSURE,)), Arm("retime", interventions=(RETIME,)))
    between_arms = _question(Intent.RUN, arms=arms, contrasts=(Contrast("closure", "retime"),))
    against_base = _question(Intent.RUN, arms=arms, contrasts=(Contrast("closure"),))
    for phase in (0, 1):
        assert needed_arms(between_arms, phase) == ("closure", "retime")
        assert needed_arms(against_base, phase) == (BASE_ARM, "closure")


def test_a_run_with_nothing_to_simulate_still_needs_the_base() -> None:
    assert needed_arms(_question(Intent.RUN), 0) == (BASE_ARM,)


MORNING = TimeWindow(7 * 3600, 9 * 3600)
NOON = TimeWindow(12 * 3600, 13 * 3600)


def _closure(window: TimeWindow) -> Intervention:
    return replace(CLOSURE, window=window)


def test_the_study_window_of_one_intervention_is_its_window() -> None:
    question = _question(interventions=(CLOSURE,))

    assert study_window(question) == EVENING


def test_the_study_window_spans_every_intervention_of_every_arm() -> None:
    question = _question(
        arms=(
            Arm("morning", interventions=(_closure(MORNING),)),
            Arm("both", interventions=(_closure(MORNING), RETIME)),
            Arm("noon", interventions=(_closure(NOON),)),
        )
    )

    assert study_window(question) == TimeWindow(7 * 3600, 20 * 3600)


def test_an_intervention_with_a_condition_adds_no_window() -> None:
    dynamic = replace(
        CLOSURE, window=None, condition=Condition(Metric.SPEED, "gv_E12_0", Operator.LT, 5.0)
    )
    question = _question(interventions=(dynamic, _closure(NOON)))

    assert study_window(question) == NOON


def test_a_question_without_interventions_has_no_study_window() -> None:
    assert study_window(_question()) is None
    assert study_window(_question(topology_changes=(NEW_EDGE,))) is None


def test_windows_past_midnight_on_the_continuous_clock_span_the_whole_night() -> None:
    before_one = TimeWindow(23 * 3600, 25 * 3600)
    after_one = TimeWindow(25.5 * 3600, 27 * 3600)
    question = _question(
        arms=(
            Arm("early", interventions=(_closure(before_one),)),
            Arm("late", interventions=(_closure(after_one),)),
        )
    )

    assert study_window(question) == TimeWindow(23 * 3600, 27 * 3600)
