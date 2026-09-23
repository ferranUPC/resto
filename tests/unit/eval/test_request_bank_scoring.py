from __future__ import annotations

from dataclasses import replace

import pytest
from eval.request_bank.bank import BankRequest, bank_requests
from eval.request_bank.concepts import (
    AmbiguousGold,
    Category,
    Concept,
    VariantSpec,
    concept_by_id,
    kmh,
    window,
)
from eval.request_bank.pipeline import VariantRecord
from eval.request_bank.scoring import (
    Rate,
    arm_structure,
    breakdown,
    consistency,
    done,
    intent_agreement,
    score_request,
    summarize,
)

from resto.domain.value_objects.arm import Arm, Contrast
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.topology_modification import AddEdge, SetLanes

W = window("08:00", "08:30")
CLOSE = Intervention(InterventionType.EDGE_CLOSURE, EdgeTarget("C0D0"), window=W)
LIMIT = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("B2C2"), params={"speed": kmh(30)}, window=W
)


def _question(**fields: object) -> Question:
    fields.setdefault("text", "q")
    fields.setdefault("intent", Intent.COMPARE)
    return Question(**fields)  # type: ignore[arg-type]


ALTERNATIVES = _question(
    arms=(Arm("closure", interventions=(CLOSE,)), Arm("limit", interventions=(LIMIT,))),
    metrics_of_interest=("mean_delay",),
)


def test_a_perfect_prediction_scores_on_every_field() -> None:
    gold = concept_by_id("R003").gold
    assert isinstance(gold, Question)
    score = score_request(gold, gold)
    assert score.valid and score.intent and score.interventions and score.topology_changes
    assert score.metrics_of_interest and score.arm_structure and score.required_arms
    assert score.multi_arm and score.spurious_ambiguity is False


def test_the_shorthand_and_a_single_arm_score_the_same() -> None:
    gold = _question(interventions=(CLOSE,))
    pred = _question(arms=(Arm("close_it", interventions=(CLOSE,)),))
    score = score_request(gold, pred)
    assert score.interventions and score.arm_structure
    assert score.used_shorthand is False
    assert score_request(gold, gold).used_shorthand is True


def test_arms_are_matched_by_content_not_by_label_or_order() -> None:
    pred = replace(
        ALTERNATIVES,
        arms=(Arm("b", interventions=(LIMIT,)), Arm("a", interventions=(CLOSE,))),
    )
    assert arm_structure(ALTERNATIVES, pred)


def test_merging_alternatives_into_one_arm_keeps_the_pieces_but_fails_the_structure() -> None:
    merged = _question(interventions=(CLOSE, LIMIT), metrics_of_interest=("mean_delay",))
    score = score_request(ALTERNATIVES, merged)
    assert score.interventions is True
    assert score.arm_structure is False
    assert score.required_arms is False


def test_contrasts_are_unordered_pairs() -> None:
    gold = replace(ALTERNATIVES, contrasts=(Contrast("closure", "limit"),))
    pred = replace(ALTERNATIVES, contrasts=(Contrast("limit", "closure"),))
    assert arm_structure(gold, pred)
    assert not arm_structure(gold, ALTERNATIVES)


def test_a_nested_contrast_against_the_wrong_reference_fails() -> None:
    new_edge = (AddEdge("C1", "D2", lanes=1, speed=kmh(50)),)
    arms = (
        Arm("edge", topology_changes=new_edge),
        Arm("edge_closure", topology_changes=new_edge, interventions=(CLOSE,)),
    )
    gold = _question(arms=arms, contrasts=(Contrast("edge"), Contrast("edge_closure", "edge")))
    pred = _question(arms=arms)
    assert not arm_structure(gold, pred)
    assert score_request(gold, pred).required_arms is True


def test_the_selective_seven_arm_request_needs_every_chosen_contrast() -> None:
    gold = concept_by_id("R065").gold
    assert isinstance(gold, Question)
    assert len(gold.arms) == 7 and len(gold.contrasts) == 5
    relabelled = replace(
        gold,
        arms=tuple(replace(a, label=f"x{i}") for i, a in enumerate(reversed(gold.arms))),
        contrasts=(),
    )
    labels = {a.label: f"x{len(gold.arms) - 1 - i}" for i, a in enumerate(gold.arms)}
    renamed = tuple(
        Contrast(labels[c.treatment], labels.get(c.reference, c.reference)) for c in gold.contrasts
    )
    assert score_request(gold, replace(relabelled, contrasts=renamed)).arm_structure
    # Everything against the base: right arms, wrong comparisons.
    against_base = score_request(gold, relabelled)
    assert against_base.required_arms and not against_base.arm_structure
    # "Does B work as well with change 2" read as against today's network instead of against B.
    wrong_reference = tuple(
        Contrast(c.treatment) if c.treatment == labels["removed_b"] else c for c in renamed
    )
    assert not score_request(gold, replace(relabelled, contrasts=wrong_reference)).arm_structure


@pytest.mark.parametrize(("speed", "ok"), [(8.34, True), (8.0, False)])
def test_params_match_within_one_percent(speed: float, ok: bool) -> None:
    gold = _question(interventions=(LIMIT,))
    pred = _question(interventions=(replace(LIMIT, params={"speed": speed}),))
    assert score_request(gold, pred).interventions is ok


def test_a_program_id_matches_as_text_or_number() -> None:
    signal = Intervention(
        InterventionType.SIGNAL_PROGRAM, TlsTarget("C2"), params={"program_id": "1"}, window=W
    )
    pred = replace(signal, params={"program_id": 1})
    score = score_request(_question(interventions=(signal,)), _question(interventions=(pred,)))
    assert score.interventions


def test_windows_are_compared_exactly() -> None:
    pred = replace(CLOSE, window=window("08:01", "08:30"))
    gold = _question(interventions=(CLOSE,))
    assert score_request(gold, _question(interventions=(pred,))).interventions is False


def test_description_is_ignored_and_custom_compares_type_target_and_window_only() -> None:
    gold = _question(interventions=(CLOSE,))
    pred = _question(interventions=(replace(CLOSE, description="roadworks"),))
    assert score_request(gold, pred).interventions
    custom = Intervention(
        InterventionType.CUSTOM, EdgeTarget("C0D0"), params={"x": 1}, window=W, description="a"
    )
    other = replace(custom, params={"x": 99}, description="b")
    score = score_request(_question(interventions=(custom,)), _question(interventions=(other,)))
    assert score.interventions


def _added(edge_id: str | None, target: str) -> Question:
    return _question(
        topology_changes=(AddEdge("B3", "C2", lanes=2, speed=kmh(50), edge_id=edge_id),),
        interventions=(
            Intervention(InterventionType.LANE_CLOSURE, LaneTarget(target, 0), window=W),
        ),
    )


def test_an_added_edge_id_only_needs_to_be_consistent() -> None:
    gold = _added("NEW1", "NEW1")
    renamed = score_request(gold, _added("X9", "X9"))
    assert renamed.interventions and renamed.topology_changes and renamed.arm_structure
    dangling = score_request(gold, _added(None, "NEW1"))
    assert not dangling.interventions and not dangling.topology_changes


def test_an_edge_id_nothing_targets_is_ignored() -> None:
    gold = _question(topology_changes=(AddEdge("B1", "C2", lanes=2, speed=kmh(50)),))
    pred = _question(
        topology_changes=(AddEdge("B1", "C2", lanes=2, speed=kmh(50), edge_id="B1C2"),)
    )
    assert score_request(gold, pred).topology_changes


def test_the_union_ignores_how_changes_are_grouped() -> None:
    wide = SetLanes("C3D3", 3)
    gold = _question(
        arms=(
            Arm("w", topology_changes=(wide,)),
            Arm("wc", topology_changes=(wide,), interventions=(CLOSE,)),
        ),
    )
    pred = _question(topology_changes=(wide,), interventions=(CLOSE,))
    score = score_request(gold, pred)
    assert score.topology_changes and score.interventions and not score.arm_structure


def test_metrics_are_an_exact_set() -> None:
    gold = _question(metrics_of_interest=("departed", "arrived"))

    def matches(*metrics: str) -> bool | None:
        return score_request(gold, _question(metrics_of_interest=metrics)).metrics_of_interest

    assert matches("arrived", "departed")
    assert not matches("arrived")
    assert not matches("Arrived", "departed")


def test_an_invalid_prediction_fails_every_graded_field() -> None:
    score = score_request(ALTERNATIVES, None)
    assert not score.valid
    assert score.intent is score.interventions is score.arm_structure is False
    assert score.used_shorthand is None


def test_an_ambiguous_gold_scores_detection_and_intent_only_when_set() -> None:
    flagged = _question(intent=Intent.COUNTERFACTUAL, ambiguities=("which edge?",))
    with_intent = score_request(AmbiguousGold("edge", Intent.COUNTERFACTUAL), flagged)
    assert with_intent.ambiguity_detected and with_intent.intent
    assert with_intent.interventions is None
    without = score_request(AmbiguousGold("gibberish"), _question())
    assert without.ambiguity_detected is False and without.intent is None


def test_summary_rates_and_done() -> None:
    scores = [score_request(ALTERNATIVES, ALTERNATIVES), score_request(ALTERNATIVES, None)]
    summary = summarize(scores)
    assert summary["schema_validity"] == Rate(1, 2)
    assert summary["arm_structure"] == Rate(1, 2)
    assert summary["ambiguity_detection"] == Rate(0, 0)
    verdict = done(summary)
    assert verdict["schema_validity"] is False
    assert verdict["ambiguity_detection"] is False


def _request(request_id: str, concept_id: str, lang: str = "en", **rest: object) -> BankRequest:
    fields: dict[str, object] = {
        "category": Category.MULTI_ARM, "split": "dev", "style": None, "vague": None,
        "noise": None, "text": "t", "gold": ALTERNATIVES,
    }
    fields.update(rest)
    return BankRequest(request_id, concept_id, lang=lang, **fields)  # type: ignore[arg-type]


def test_breakdown_groups_by_axis() -> None:
    requests = [_request("C1", "C1"), _request("C1.ca", "C1", "ca"), _request("C1.es", "C1", "es")]
    scores = {
        "C1": score_request(ALTERNATIVES, ALTERNATIVES),
        "C1.ca": score_request(ALTERNATIVES, None),
    }
    by_lang = breakdown(requests, scores, "lang")
    assert set(by_lang) == {"ca", "en"}
    assert by_lang["ca"]["schema_validity"] == Rate(0, 1)


def test_consistency_is_agreement_between_variants_not_correctness() -> None:
    wrong = _question(interventions=(CLOSE, LIMIT), metrics_of_interest=("mean_delay",))
    requests = [
        _request("A", "A"), _request("A.ca", "A", "ca"),
        _request("B", "B"), _request("B.ca", "B", "ca"),
        _request("B.en-vague_time", "B", vague="time"),
    ]
    predictions = {
        "A": wrong, "A.ca": replace(wrong, text="other"),
        "B": ALTERNATIVES, "B.ca": wrong, "B.en-vague_time": None,
    }
    assert consistency(requests, predictions) == Rate(1, 2)


def test_intent_agreement_across_runs() -> None:
    compare = _question()
    describe = _question(intent=Intent.DESCRIBE)
    runs: list[dict[str, Question | None]] = [
        {"a": compare, "b": compare}, {"a": compare, "b": describe}, {"a": compare, "b": None},
    ]
    assert intent_agreement(runs) == Rate(1, 2)


def _record(concept: Concept, spec: VariantSpec, text: str, verified: bool) -> VariantRecord:
    return VariantRecord(
        id=concept.variant_id(spec), concept_id=concept.id, lang=spec.lang, style=spec.style,
        vague=spec.vague, noise=spec.noise, text=text, generated=text, back_translation=None,
        verified=verified,
    )


def test_the_bank_holds_bases_and_verified_variants_only() -> None:
    concept = concept_by_id("R001")
    ca, es, vague = concept.variants[0], concept.variants[1], concept.variants[6]
    records = {
        r.id: r for r in (
            _record(concept, ca, "Tanca el carril", True),
            _record(concept, es, "Cierra el carril", False),
            _record(concept, vague, "Cierra el carril por la mañana", True),
        )
    }
    requests = bank_requests((concept,), records)
    assert [r.id for r in requests] == ["R001", "R001.ca", "R001.es-vague_time"]
    assert isinstance(requests[1].gold, Question) and requests[1].gold.text == "Tanca el carril"
    assert isinstance(requests[2].gold, AmbiguousGold)
