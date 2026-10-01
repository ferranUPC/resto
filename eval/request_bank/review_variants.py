"""Review page for regenerated variants (E3.11 ticket 05). Local only, no network.

    python -m eval.request_bank.review_variants build   # writes review_variants.html
    python -m eval.request_bank.review_variants apply decisions.json

The page lists the variants that need a human decision: every variant of a spread-demand concept
(is the demand still said in pieces?) and every variant that failed verification (accept it, with an
optional corrected text, or leave it out). It saves your choices in the browser and exports a
`decisions.json`, which `apply` writes into `variants.json`.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from eval.request_bank.concepts import CONCEPTS
from eval.request_bank.generate import VARIANTS_PATH, load_variants, save_variants
from eval.request_bank.pipeline import VariantRecord

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "review_variants_template.html"
OUTPUT = HERE / "review_variants.html"
_PLACEHOLDER = "/*__ITEMS__*/[]"


def review_items(records: dict[str, VariantRecord]) -> list[dict[str, Any]]:
    items = []
    for concept in CONCEPTS:
        for spec in concept.variants:
            record = records.get(concept.variant_id(spec))
            if record is None or not (concept.spread_demand or not record.verified):
                continue
            items.append(
                {
                    "id": record.id,
                    "concept": concept.id,
                    "original": concept.text,
                    "gold_demand": getattr(concept.gold, "demand_ref", None),
                    "text": record.text,
                    "back_translation": record.back_translation,
                    "spread": concept.spread_demand,
                    "failed": not record.verified,
                    "differences": list(record.differences),
                }
            )
    return items


def render(items: list[dict[str, Any]]) -> str:
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace(_PLACEHOLDER, payload)


def apply_decisions(
    records: dict[str, VariantRecord], decisions: list[dict[str, Any]]
) -> dict[str, VariantRecord]:
    """`spread` true/false sets `demand_still_spread`; `accept` marks a failed variant verified,
    with the corrected `text` if given."""
    out = dict(records)
    for d in decisions:
        record = out[d["id"]]
        if d.get("spread") is not None:
            record = replace(record, demand_still_spread=d["spread"])
        if d.get("accept"):
            record = replace(
                record,
                verified=True,
                text=d.get("text") or record.text,
                notes=(*record.notes, "accepted by the reviewer after a failed verification"),
            )
        out[record.id] = record
    return out


def main(argv: list[str]) -> int:
    if argv[:1] == ["build"]:
        items = review_items(load_variants())
        OUTPUT.write_text(render(items), encoding="utf-8")
        print(f"{OUTPUT} written with {len(items)} variants to review")
        return 0
    if len(argv) == 2 and argv[0] == "apply":
        decisions = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        save_variants(apply_decisions(load_variants(), decisions), VARIANTS_PATH)
        print(f"{len(decisions)} decisions written to {VARIANTS_PATH.name}")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
