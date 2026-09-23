"""The request bank as the Parser benchmark reads it: every concept's base request plus its frozen,
verified variants, each with its gold and the axes the report breaks down by."""

from __future__ import annotations

from dataclasses import dataclass

from eval.request_bank.concepts import (
    CONCEPTS,
    SPLITS,
    Category,
    Concept,
    Gold,
    Noise,
    Style,
    Vague,
)
from eval.request_bank.generate import load_variants
from eval.request_bank.pipeline import VariantRecord


@dataclass(frozen=True, slots=True)
class BankRequest:
    id: str
    concept_id: str
    category: Category
    split: str
    lang: str
    style: Style | None
    vague: Vague | None
    noise: Noise | None
    text: str
    gold: Gold


def bank_requests(
    concepts: tuple[Concept, ...] = CONCEPTS,
    variants: dict[str, VariantRecord] | None = None,
) -> list[BankRequest]:
    """Base requests and verified variants; a variant not yet generated or not verified is left
    out, so a partial bank can be scored while it is being built."""
    records = load_variants() if variants is None else variants
    requests = []
    for concept in concepts:
        split = SPLITS.get(concept.id, "dev")
        requests.append(
            BankRequest(
                concept.id, concept.id, concept.category, split, "en", None, None, None,
                concept.text, concept.gold,
            )
        )
        for spec in concept.variants:
            record = records.get(concept.variant_id(spec))
            if record is None or not record.verified:
                continue
            requests.append(
                BankRequest(
                    record.id, concept.id, concept.category, split, spec.lang, spec.style,
                    spec.vague, spec.noise, record.text, concept.gold_for(spec, record.text),
                )
            )
    return requests
