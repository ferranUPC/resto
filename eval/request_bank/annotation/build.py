"""Writes `annotate.html`: the annotation page with the held-out concepts' English base requests
embedded, in a fixed shuffled order and without their category or gold.

Only the text goes into the page. The annotator sees none of the bank's wording conventions (they
live in `concepts.py` and the Parser prompt), so their reading is independent of the author's.

    python -m eval.request_bank.annotation.build
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from eval.request_bank.concepts import CONCEPTS, SPLITS

HERE = Path(__file__).parent
TEMPLATE = HERE / "template.html"
OUTPUT = HERE / "annotate.html"
SEED = 20260924
_PLACEHOLDER = "/*__ITEMS__*/[]"


def held_out_items(seed: int = SEED) -> list[dict[str, str]]:
    items = [
        {"concept_id": c.id, "text": c.text} for c in CONCEPTS if SPLITS.get(c.id) == "held_out"
    ]
    random.Random(seed).shuffle(items)
    return items


def render(template: str, items: list[dict[str, str]]) -> str:
    if _PLACEHOLDER not in template:
        raise ValueError(f"template has no {_PLACEHOLDER} placeholder")
    # `</` is escaped so a request text can never close the <script> element.
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(_PLACEHOLDER, payload)


def main() -> None:
    items = held_out_items()
    OUTPUT.write_text(render(TEMPLATE.read_text(encoding="utf-8"), items), encoding="utf-8")
    print(f"{OUTPUT} written with {len(items)} held-out requests")


if __name__ == "__main__":
    main()
