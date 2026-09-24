from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from eval.request_bank.annotation.agreement import (
    FORMAT,
    cohen_kappa,
    external_requests,
    pairwise,
    parse_export,
    render,
    score_against_gold,
)
from eval.request_bank.annotation.build import TEMPLATE, held_out_items
from eval.request_bank.annotation.build import render as render_page
from eval.request_bank.concepts import SPLITS, AmbiguousGold, concept_by_id

from resto.application.schemas import adapter_for
from resto.domain.value_objects.question import Intent, Question


def _dump(question: Question) -> dict[str, Any]:
    return adapter_for(Question).dump_python(question, mode="json")


def _item(concept_id: str, question: dict[str, Any] | None, done: bool = True) -> dict[str, Any]:
    return {
        "source": "held_out", "concept_id": concept_id, "text": concept_by_id(concept_id).text,
        "done": done, "question": question, "issues": [], "notes": "", "form": {},
    }


def _export(annotator: str, items: list[dict[str, Any]], external: list[Any] | None = None):
    return {"format": FORMAT, "annotator": annotator, "exported_at": "t", "held_out": items,
            "external": external or []}


def _gold_question(concept_id: str) -> Question:
    gold = concept_by_id(concept_id).gold
    assert isinstance(gold, Question)
    return gold


# --- the page ------------------------------------------------------------------------------------


def test_the_page_carries_every_held_out_concept_and_nothing_else():
    items = held_out_items()
    assert sorted(i["concept_id"] for i in items) == sorted(
        c for c, split in SPLITS.items() if split == "held_out"
    )
    assert set(items[0]) == {"concept_id", "text"}  # no category, no gold


def test_the_page_order_is_shuffled_and_fixed():
    assert held_out_items() == held_out_items()
    ids = [i["concept_id"] for i in held_out_items()]
    assert ids != sorted(ids)


def test_a_request_text_cannot_close_the_script_element():
    page = render_page("<script>const X = /*__ITEMS__*/[];</script>",
                       [{"concept_id": "R1", "text": "a </script> b"}])
    assert page.count("</script>") == 1


def test_the_template_has_the_items_placeholder():
    assert "/*__ITEMS__*/[]" in TEMPLATE.read_text(encoding="utf-8")


# --- scoring against gold ------------------------------------------------------------------------


def test_an_annotation_equal_to_gold_agrees_on_every_field():
    export = parse_export(_export("a", [
        _item("R027", _dump(_gold_question("R027"))),
        _item("R033", _dump(_gold_question("R033"))),
    ]))
    for _, _, score in score_against_gold(export):
        assert score.intent and score.interventions and score.topology_changes
        assert score.metrics_of_interest and not score.spurious_ambiguity
        assert score.arm_structure


def test_a_clear_reading_of_an_ambiguous_concept_misses_the_ambiguity():
    assert isinstance(concept_by_id("R042").gold, AmbiguousGold)
    guess = Question(text="t", intent=Intent.COUNTERFACTUAL, network_ref="DEV-NET")
    export = parse_export(_export("a", [_item("R042", _dump(guess))]))
    [(_, _, score)] = score_against_gold(export)
    assert score.ambiguity_detected is False
    assert "R042" in render([export])


def test_annotations_not_marked_done_are_not_scored():
    export = parse_export(_export("a", [_item("R033", _dump(_gold_question("R033")), done=False)]))
    assert score_against_gold(export) == []


def test_a_database_submission_is_read_like_a_file_export():
    payload = _export("a", [_item("R033", _dump(_gold_question("R033")))])
    export = parse_export({"annotator": "a", "exported_at": "t", "payload": json.dumps(payload)})
    assert export.annotator == "a" and len(export.held_out) == 1


def test_another_format_is_refused():
    with pytest.raises(ValueError):
        parse_export({"format": "other", "held_out": []})


# --- between annotators --------------------------------------------------------------------------


def test_kappa_is_one_on_perfect_agreement_and_zero_at_chance():
    assert cohen_kappa([("a", "a"), ("b", "b")]) == 1.0
    assert cohen_kappa([("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")]) == 0.0
    assert cohen_kappa([("a", "a")]) is None
    assert cohen_kappa([]) is None


def test_pairwise_compares_only_concepts_both_marked_done():
    same = _dump(_gold_question("R033"))
    a = parse_export(_export("a", [_item("R033", same), _item("R027", same)]))
    b = parse_export(_export("b", [_item("R033", same), _item("R027", same, done=False)]))
    result = pairwise(a, b)
    assert result["shared"] == 1
    assert result["intent"].value == 1.0
    assert result["arm_structure"].value == 1.0


# --- external requests ---------------------------------------------------------------------------


def test_external_requests_keep_only_finished_ones_with_their_authors_gold(tmp_path: Path):
    question = _dump(Question(text="x", intent=Intent.DESCRIBE, network_ref="DEV-NET"))
    export = parse_export(_export("ana", [], external=[
        {"id": "N01", "text": "x", "done": True, "question": question, "notes": ""},
        {"id": "N02", "text": "y", "done": False, "question": question, "notes": ""},
        {"id": "N03", "text": "", "done": True, "question": question, "notes": ""},
    ]))
    [request] = external_requests([export])
    assert request["id"] == "X-ana-N01" and request["question"] == question
