"""Generate request-bank variants (work-plan E3.4). Spends API credit: run by hand only.

    python -m eval.request_bank.generate --dry-run
    python -m eval.request_bank.generate --concepts R001 R002 --max-cost-usd 0.05
    python -m eval.request_bank.generate --report-only

Variants are frozen in `variants.json` (committed): an existing variant is never regenerated
unless `--regenerate` names it. `review.md` lists every variant for human review — the verifier's
failures, plus a fixed ~15 % sample of its passes. Run inside the `resto` conda env with
`OPENROUTER_API_KEY` in `.env`.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.request_bank.concepts import CONCEPTS, SPLITS, AmbiguousGold, Concept, VariantSpec
from eval.request_bank.pipeline import Chat, Models, VariantRecord, generate_variant
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.topology_modification import TopologyModification

HERE = Path(__file__).resolve().parent
VARIANTS_PATH = HERE / "variants.json"
REVIEW_PATH = HERE / "review.md"
SAMPLE_RATE = 0.15
_TOKENS_PER_CALL = (450, 200)


def load_variants(path: Path = VARIANTS_PATH) -> dict[str, VariantRecord]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        r["id"]: VariantRecord(
            **{**r, "differences": tuple(r["differences"]), "notes": tuple(r["notes"])}
        )
        for r in rows
    }


def save_variants(records: dict[str, VariantRecord], path: Path = VARIANTS_PATH) -> None:
    rows = [asdict(records[k]) for k in sorted(records)]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pending(
    concepts: tuple[Concept, ...], existing: dict[str, VariantRecord], regenerate: set[str]
) -> list[tuple[Concept, VariantSpec]]:
    return [
        (c, v)
        for c in concepts
        for v in c.variants
        if c.variant_id(v) not in existing or c.variant_id(v) in regenerate
    ]


def estimate_usd(todo: list[tuple[Concept, VariantSpec]], models: Models) -> float:
    from eval.request_bank.llm import price_of

    pin, pout = _TOKENS_PER_CALL
    total = 0.0
    for _, spec in todo:
        if not spec.needs_llm:
            continue
        generator_calls = 2 if spec.lang != "en" else 1
        total += generator_calls * price_of(models.generator, pin, pout)
        total += price_of(models.verifier, pin, pout)
    return total


def run(
    todo: list[tuple[Concept, VariantSpec]],
    records: dict[str, VariantRecord],
    chat: Chat,
    models: Models,
    max_cost_usd: float,
    save: Any = save_variants,
) -> float:
    spent = 0.0
    for concept, spec in todo:
        if spent >= max_cost_usd:
            print(f"cost cap reached (${spent:.4f}); stopping", file=sys.stderr)
            break
        record = generate_variant(concept, spec, chat, models)
        records[record.id] = record
        spent += record.cost_usd
        save(records)
        mark = "ok  " if record.verified else "FAIL"
        print(f"{mark} {record.id}  ${record.cost_usd:.5f}")
    return spent


def _clock(seconds: float) -> str:
    return f"{int(seconds // 3600):02d}:{int(seconds % 3600 // 60):02d}"


def _item(item: Intervention | TopologyModification) -> str:
    if not isinstance(item, Intervention):
        fields = {k: v for k, v in asdict(item).items() if k != "kind" and v is not None}
        return f"{item.kind}(" + ", ".join(f"{k}={v}" for k, v in fields.items()) + ")"
    target = item.target and "/".join(str(v) for k, v in asdict(item.target).items() if k != "kind")
    text = f"{item.type}({target or ''}" + "".join(f", {k}={v}" for k, v in item.params.items())
    if item.window is not None:
        text += f", {_clock(item.window.start)}–{_clock(item.window.end)}"
    if item.condition is not None:
        c = item.condition
        text += f", when {c.metric}({c.target}) {c.op} {c.value:g}"
    return text + ")"


def _gold_summary(concept: Concept) -> str:
    gold = concept.gold
    if isinstance(gold, AmbiguousGold):
        intent = f", intent `{gold.intent}`" if gold.intent else ""
        return f"expect `ambiguities[]` ({gold.reason}{intent})"
    parts = [f"intent `{gold.intent}`"]
    if gold.network_ref:
        parts.append(f"network `{gold.network_ref}`")
    if gold.demand_ref:
        parts.append(f"demand `{gold.demand_ref}`")
    if gold.time_window:
        parts.append(f"window {_clock(gold.time_window.start)}–{_clock(gold.time_window.end)}")
    if gold.metrics_of_interest:
        parts.append("metrics " + ", ".join(gold.metrics_of_interest))
    lines = [" · ".join(parts)]
    for arm in gold.effective_arms:
        items = [*arm.topology_changes, *arm.interventions]
        lines.append(f"- arm `{arm.label}`: " + " + ".join(f"`{_item(i)}`" for i in items))
    if gold.arms:
        lines.append(
            "- contrasts: "
            + ", ".join(f"`{c.treatment}` vs `{c.reference}`" for c in gold.effective_contrasts)
        )
    return "\n".join(lines)


def render_review(records: dict[str, VariantRecord]) -> str:
    rng = random.Random(0)
    lines = ["# Request bank — variant review", ""]
    generated = [r for r in records.values() if r.generated is not None]
    failed = [r for r in generated if not r.verified]
    lines += [
        f"{len(records)} variants, {len(generated)} LLM-generated, {len(failed)} failed "
        f"verification, total cost ${sum(r.cost_usd for r in records.values()):.4f}.",
        "",
        "Review every **FAIL** and every **SAMPLE**; fix a variant by editing its `text` in "
        "`variants.json`.",
        "",
    ]
    for concept in CONCEPTS:
        rows = [records[concept.variant_id(v)] for v in concept.variants
                if concept.variant_id(v) in records]
        lines += [
            f"## {concept.id} · {concept.category} · {SPLITS[concept.id]}",
            "",
            f"> {concept.text}",
            "",
            f"Gold: {_gold_summary(concept)}",
            "",
        ]
        if not rows:
            lines += ["_No variants generated yet._", ""]
        for r in rows:
            if not r.verified:
                tag = "FAIL"
            elif r.generated is not None and rng.random() < SAMPLE_RATE:
                tag = "SAMPLE"
            else:
                tag = "ok"
            lines.append(f"### `{r.id}` — {tag}")
            lines.append("")
            lines.append(f"- text: {r.text}")
            if r.back_translation:
                lines.append(f"- back-translation: {r.back_translation}")
            for d in r.differences:
                lines.append(f"- verifier: {d}")
            lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--concepts", nargs="*", help="concept ids (default: all)")
    parser.add_argument("--max-cost-usd", type=float, default=0.0)
    parser.add_argument("--regenerate", nargs="*", default=[], help="variant ids to redo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    from eval.request_bank.llm import bank_models

    models = bank_models()
    concepts = tuple(c for c in CONCEPTS if not args.concepts or c.id in args.concepts)
    records = load_variants()
    todo = pending(concepts, records, set(args.regenerate))

    if not args.report_only:
        estimate = estimate_usd(todo, models)
        print(f"{len(todo)} variants to generate, estimated ${estimate:.4f} "
              f"(generator {models.generator}, verifier {models.verifier})")
        if args.dry_run:
            return 0
        if estimate > 1.0:
            print("estimate above $1: log it in docs/evaluating-resto.md §7 instead (CLAUDE.md)",
                  file=sys.stderr)
            return 2
        if todo and args.max_cost_usd <= 0:
            print("pass --max-cost-usd", file=sys.stderr)
            return 2
        from eval.request_bank.llm import OpenRouterChat

        spent = run(todo, records, OpenRouterChat(), models, args.max_cost_usd)
        print(f"spent ${spent:.4f}")

    REVIEW_PATH.write_text(render_review(records) + "\n", encoding="utf-8")
    print(f"review: {REVIEW_PATH.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
