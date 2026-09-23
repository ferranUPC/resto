from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from eval.request_bank.concepts import (
    CONCEPTS,
    LANGUAGES,
    SPLITS,
    AmbiguousGold,
    Category,
    Concept,
    Noise,
    Style,
    Vague,
    VariantSpec,
    _v,
    clock,
    concept_by_id,
)
from eval.request_bank.generate import load_variants, pending, render_review, run, save_variants
from eval.request_bank.noise import add_typos, strip_accents
from eval.request_bank.pipeline import Models, Reply, generate_variant, parse_verdict

from resto.application.schemas import adapter_for
from resto.domain.value_objects.question import Intent, Question

MODELS = Models(generator="gen", verifier="ver")


@dataclass
class FakeChat:
    verdict: str = '{"same_meaning": true, "differences": []}'
    calls: list[tuple[str, str]] = field(default_factory=list)

    def __call__(self, model: str, system: str, user: str) -> Reply:
        self.calls.append((model, user))
        if model == "ver":
            return Reply(self.verdict, cost_usd=0.001)
        if user.startswith("Translate"):
            return Reply("back in English", cost_usd=0.001)
        return Reply("  rewritten text  ", cost_usd=0.001)


def _concept(**overrides: object) -> Concept:
    text = "Close lane 1 of B0C0."
    fields: dict[str, object] = {
        "id": "T001",
        "category": Category.SINGLE,
        "text": text,
        "gold": Question(text=text, intent=Intent.COUNTERFACTUAL),
        "variants": (VariantSpec("ca"),),
    }
    fields.update(overrides)
    return Concept(**fields)  # type: ignore[arg-type]


def test_every_concept_builds_and_has_unique_ids() -> None:
    ids = [c.id for c in CONCEPTS]
    assert len(set(ids)) == len(ids)
    assert concept_by_id(ids[0]) is CONCEPTS[0]


def test_every_category_and_axis_value_has_at_least_15_variants() -> None:
    variants = [(c, v) for c in CONCEPTS for v in c.variants]
    by_category = Counter(c.category for c, _ in variants)
    assert all(by_category[category] >= 15 for category in Category), by_category
    axes = Counter(
        axis for _, v in variants for axis in (v.lang, v.style, v.noise) if axis not in (None, "en")
    )
    expected = {*LANGUAGES} - {"en"} | {*Style} | {*Noise}
    assert all(axes[value] >= 15 for value in expected), axes


def test_the_split_is_close_to_70_30_and_every_category_is_held_out() -> None:
    held_out = [c for c in CONCEPTS if SPLITS[c.id] == "held_out"]
    assert 0.25 <= len(held_out) / len(CONCEPTS) <= 0.35
    assert {c.category for c in held_out} == set(Category)


def test_gold_shapes_follow_the_category() -> None:
    for concept in CONCEPTS:
        gold = concept.gold
        ambiguous = concept.category in (
            Category.AMBIGUOUS, Category.UNINTELLIGIBLE, Category.OUT_OF_SCOPE
        )
        assert isinstance(gold, AmbiguousGold) is ambiguous or (
            concept.category is Category.ADVERSARIAL
        ), concept.id
        if not isinstance(gold, Question):
            continue
        arms = gold.effective_arms
        if concept.category is Category.MULTI_ARM:
            assert len(arms) >= 2, concept.id
        if concept.category is Category.COMBINED:
            assert len(arms) == 1, concept.id
            assert len(arms[0].topology_changes) + len(arms[0].interventions) >= 2, concept.id
        if any(v.vague is Vague.GROUPING for v in concept.variants):
            changes = {c for a in arms for c in a.topology_changes}
            assert len(changes) + sum(len(a.interventions) for a in arms) >= 2, concept.id


def test_gold_questions_round_trip_through_the_schema() -> None:
    adapter = adapter_for(Question)
    for concept in CONCEPTS:
        if isinstance(concept.gold, Question):
            assert adapter.validate_json(adapter.dump_json(concept.gold)) == concept.gold


def test_variant_keys_parse_back_to_specs() -> None:
    specs = _v("ca", "es-colloquial-no_accents", "en-vague_place")
    assert [s.key for s in specs] == ["ca", "es-colloquial-no_accents", "en-vague_place"]


def test_clock_times_are_seconds_since_midnight() -> None:
    assert clock("08:00") == 28800.0
    assert clock("08:30") == 30600.0


def test_the_plain_english_variant_is_the_concept_itself() -> None:
    with pytest.raises(ValueError):
        VariantSpec("en")


def test_variant_keys_name_every_axis() -> None:
    spec = VariantSpec("es", style=Style.MESSY, vague=Vague.TIME, noise=Noise.TYPOS)
    assert spec.key == "es-messy-vague_time-typos"


def test_the_gold_question_must_carry_the_concept_text() -> None:
    with pytest.raises(ValueError):
        _concept(gold=Question(text="something else", intent=Intent.DESCRIBE))


def test_an_ambiguous_concept_cannot_be_vaguised() -> None:
    with pytest.raises(ValueError):
        _concept(gold=AmbiguousGold("unclear"), variants=(VariantSpec("ca", vague=Vague.TIME),))


def test_a_variant_keeps_the_gold_with_its_own_text() -> None:
    concept = _concept()
    gold = concept.gold_for(VariantSpec("ca"), "Tanca el carril 1 de B0C0.")
    assert isinstance(gold, Question)
    assert gold.text == "Tanca el carril 1 de B0C0."
    assert gold.intent is Intent.COUNTERFACTUAL


def test_a_vaguised_variant_expects_an_ambiguity_and_keeps_the_intent() -> None:
    gold = _concept().gold_for(VariantSpec("es", vague=Vague.TIME), "Cierra B0C0 por la mañana")
    assert gold == AmbiguousGold(reason="vague time", intent=Intent.COUNTERFACTUAL)


def test_typos_are_reproducible_and_never_touch_tokens_with_digits() -> None:
    text = "Close lane 1 of edge B0C0 from 08:00 to 08:30 and measure travelling times"
    noisy = add_typos(text, "seed", rate=1.0)
    assert noisy == add_typos(text, "seed", rate=1.0)
    assert noisy != text
    for token in ("B0C0", "08:00", "08:30", "1"):
        assert token in noisy


def test_strip_accents_keeps_letters() -> None:
    assert strip_accents("¿Qué pasaría si cierro el carril?") == "¿Que pasaria si cierro el carril?"


def test_noise_only_english_variant_makes_no_llm_call() -> None:
    chat = FakeChat()
    concept = _concept(variants=(VariantSpec("en", noise=Noise.TYPOS),))
    record = generate_variant(concept, concept.variants[0], chat, MODELS)
    assert chat.calls == []
    assert record.verified and record.generated is None and record.cost_usd == 0


def test_translated_variant_is_generated_back_translated_and_verified() -> None:
    chat = FakeChat()
    concept = _concept()
    record = generate_variant(concept, concept.variants[0], chat, MODELS)
    assert [m for m, _ in chat.calls] == ["gen", "gen", "ver"]
    assert record.text == "rewritten text"
    assert record.back_translation == "back in English"
    assert record.verified
    assert record.cost_usd == pytest.approx(0.003)


def test_english_variant_is_not_back_translated() -> None:
    chat = FakeChat()
    concept = _concept(variants=(VariantSpec("en", style=Style.TELEGRAPHIC),))
    record = generate_variant(concept, concept.variants[0], chat, MODELS)
    assert [m for m, _ in chat.calls] == ["gen", "ver"]
    assert record.back_translation is None


def test_noise_is_applied_after_the_verifier_saw_the_clean_text() -> None:
    concept = _concept(variants=(VariantSpec("es", noise=Noise.NO_ACCENTS),))
    chat_text = "Cierra el carril 1 de B0C0 según el plan"

    def reply(model: str, system: str, user: str) -> Reply:
        if model == "ver":
            assert chat_text in user
            return Reply('{"same_meaning": true}')
        return Reply(chat_text)

    record = generate_variant(concept, concept.variants[0], reply, MODELS)
    assert record.generated == chat_text
    assert record.text == "Cierra el carril 1 de B0C0 segun el plan"


def test_verifier_failure_is_recorded_with_its_differences() -> None:
    chat = FakeChat(verdict='```json\n{"same_meaning": false, "differences": ["lane 2"]}\n```')
    concept = _concept()
    record = generate_variant(concept, concept.variants[0], chat, MODELS)
    assert not record.verified
    assert record.differences == ("lane 2",)


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ('{"target_is_vague": true, "rest_same": true}', True),
        ('{"target_is_vague": false, "rest_same": true}', False),
        ('{"target_is_vague": true, "rest_same": false}', False),
        ("not json", False),
    ],
)
def test_vague_verdicts_need_both_checks(text: str, ok: bool) -> None:
    verified, differences = parse_verdict(text, VariantSpec("es", vague=Vague.TIME))
    assert verified is ok
    if text == "not json":
        assert differences == ("unparseable verifier output",)


def test_a_variant_identical_to_the_original_fails_whatever_the_verifier_says() -> None:
    concept = _concept(variants=(VariantSpec("en", vague=Vague.TIME),))

    def reply(model: str, system: str, user: str) -> Reply:
        if model == "ver":
            return Reply('{"target_is_vague": true, "rest_same": true}')
        return Reply("close lane 1 of  B0C0.")

    record = generate_variant(concept, concept.variants[0], reply, MODELS)
    assert not record.verified
    assert record.differences[0] == "the variant is the original text"


def test_a_variant_written_as_the_assistant_fails() -> None:
    verified, differences = parse_verdict(
        '{"is_user_request": false, "same_meaning": true}', VariantSpec("ca")
    )
    assert not verified
    assert differences == ("not written as a user request",)


def test_python_style_booleans_are_parsed() -> None:
    verified, _ = parse_verdict('{"same_meaning": True, "differences": []}', VariantSpec("ca"))
    assert verified


def test_the_verifier_sees_the_back_translation() -> None:
    chat = FakeChat()
    concept = _concept()
    generate_variant(concept, concept.variants[0], chat, MODELS)
    verifier_prompt = chat.calls[-1][1]
    assert "back in English" in verifier_prompt


def test_blurring_the_grouping_also_drops_the_intent() -> None:
    gold = _concept().gold_for(VariantSpec("en", vague=Vague.GROUPING), "close A and B")
    assert gold == AmbiguousGold(reason="vague grouping", intent=None)


def test_run_skips_frozen_variants_and_stops_at_the_cost_cap(tmp_path: Path) -> None:
    concept = _concept(variants=(VariantSpec("ca"), VariantSpec("es"), VariantSpec("de")))
    first = generate_variant(concept, concept.variants[0], FakeChat(), MODELS)
    records = {first.id: first}
    todo = pending((concept,), records, set())
    assert [concept.variant_id(v) for _, v in todo] == ["T001.es", "T001.de"]

    path = tmp_path / "variants.json"
    spent = run(todo, records, FakeChat(), MODELS, max_cost_usd=0.002,
                save=lambda r: save_variants(r, path))
    assert spent == pytest.approx(0.003)
    assert set(load_variants(path)) == {"T001.ca", "T001.es"}


def test_regenerate_redoes_a_frozen_variant() -> None:
    concept = _concept()
    record = generate_variant(concept, concept.variants[0], FakeChat(), MODELS)
    assert pending((concept,), {record.id: record}, {record.id}) == [(concept, concept.variants[0])]


def test_review_lists_failures() -> None:
    concept = CONCEPTS[0]
    spec = concept.variants[0]
    record = generate_variant(concept, spec, FakeChat(verdict='{"same_meaning": false}'), MODELS)
    review = render_review({record.id: record})
    assert f"`{record.id}` — FAIL" in review
