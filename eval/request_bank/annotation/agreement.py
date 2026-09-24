"""Scores blind human annotations of the held-out concepts against the bank's gold, and between
annotators, with the Parser benchmark's own rules (`score_request`), so a human and the Parser are
measured the same way. Also collects the external requests the annotators wrote, with their own
annotation as gold.

Accepts the page's JSON export, or a `submissions/<annotator>` document read from the published
page's database (its `payload` field holds the same export as a string).

    python -m eval.request_bank.annotation.agreement exports/*.json --out report.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from eval.request_bank.concepts import ALSO_ACCEPTED, CONCEPTS, AmbiguousGold, Concept
from eval.request_bank.generate import describe_question
from eval.request_bank.scoring import Rate, RequestScore, arm_structure, score_request, summarize
from resto.application.schemas import adapter_for
from resto.domain.value_objects.question import Question

FORMAT = "resto-annotation/v1"
GRADED = (
    "intent",
    "interventions",
    "topology_changes",
    "metrics_of_interest",
    "ambiguity_detection",
    "arm_structure",
)
REPORTED = ("intent_strict", "spurious_ambiguity", "network_ref", "demand_ref", "time_window")


@dataclass(frozen=True, slots=True)
class Annotation:
    annotator: str
    concept_id: str
    done: bool
    question: Question | None
    notes: str
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Export:
    annotator: str
    held_out: tuple[Annotation, ...]
    external: tuple[dict[str, Any], ...]


def parse_export(data: Mapping[str, Any]) -> Export:
    if "payload" in data and "format" not in data:
        data = json.loads(data["payload"])
    if data.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} export")
    annotator = str(data.get("annotator") or "anonymous")
    adapter = adapter_for(Question)
    held = tuple(
        Annotation(
            annotator=annotator,
            concept_id=item["concept_id"],
            done=bool(item.get("done")),
            question=None if item.get("question") is None
            else adapter.validate_python(item["question"]),
            notes=item.get("notes", ""),
            issues=tuple(item.get("issues", ())),
        )
        for item in data.get("held_out", ())
    )
    return Export(annotator, held, tuple(data.get("external", ())))


def load_export(path: Path) -> Export:
    return parse_export(json.loads(path.read_text(encoding="utf-8")))


def _gold_lines(concept: Concept) -> list[str]:
    gold = concept.gold
    if isinstance(gold, AmbiguousGold):
        intent = f", intent `{gold.intent}`" if gold.intent else ""
        return [f"expect `ambiguities[]` ({gold.reason}{intent})"]
    return describe_question(gold)


def _pct(rate: Rate) -> str:
    value = rate.value
    return "—" if value is None else f"{100 * value:.0f} % ({rate.hits}/{rate.total})"


def score_against_gold(
    export: Export, concepts: Sequence[Concept] = CONCEPTS
) -> list[tuple[Annotation, Concept, RequestScore]]:
    """Only annotations marked done are scored."""
    by_id = {c.id: c for c in concepts}
    return [
        (
            a, by_id[a.concept_id],
            score_request(
                by_id[a.concept_id].gold, a.question,
                ALSO_ACCEPTED.get(a.concept_id, frozenset()),
            ),
        )
        for a in export.held_out
        if a.done and a.concept_id in by_id
    ]


# --- between annotators --------------------------------------------------------------------------


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Agreement between two raters beyond chance; None when it is undefined."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in left.keys() | right.keys()) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def pairwise(a: Export, b: Export) -> dict[str, Any]:
    """Intent and ambiguity flag on every concept both marked done; arm structure where neither
    found the request ambiguous and both wrote a treatment."""
    ours = {x.concept_id: x.question for x in a.held_out if x.done and x.question}
    theirs = {x.concept_id: x.question for x in b.held_out if x.done and x.question}
    shared = sorted(ours.keys() & theirs.keys())
    intents = [(str(ours[c].intent), str(theirs[c].intent)) for c in shared]
    flags = [(str(ours[c].is_ambiguous), str(theirs[c].is_ambiguous)) for c in shared]
    arms = [
        arm_structure(ours[c], theirs[c])
        for c in shared
        if not ours[c].is_ambiguous and not theirs[c].is_ambiguous
        and ours[c].effective_arms and theirs[c].effective_arms
    ]
    return {
        "annotators": (a.annotator, b.annotator),
        "shared": len(shared),
        "intent": Rate(sum(x == y for x, y in intents), len(intents)),
        "intent_kappa": cohen_kappa(intents),
        "ambiguous": Rate(sum(x == y for x, y in flags), len(flags)),
        "ambiguous_kappa": cohen_kappa(flags),
        "arm_structure": Rate(sum(arms), len(arms)),
    }


# --- report --------------------------------------------------------------------------------------


def _ambiguity_ok(score: RequestScore) -> bool | None:
    """Ambiguous gold: did the annotator ask? Clear gold: did they refrain from asking?"""
    if score.ambiguity_detected is not None:
        return score.ambiguity_detected
    return None if score.spurious_ambiguity is None else not score.spurious_ambiguity


def _mark(value: bool | None) -> str:
    return "—" if value is None else ("✓" if value else "✗")


def render(exports: Sequence[Export], concepts: Sequence[Concept] = CONCEPTS) -> str:
    lines = [
        "# Held-out blind annotation — agreement with the bank's gold",
        "",
        "Each annotation is scored with the Parser benchmark's `score_request`, so the rates below "
        "read like a Parser report: how often a person, reading the request without the bank's "
        "wording conventions, lands on the gold.",
        "",
    ]
    for export in exports:
        scored = score_against_gold(export, concepts)
        summary = summarize([s for _, _, s in scored])
        lines += [
            f"## {export.annotator}",
            "",
            f"{len(scored)} of {len(export.held_out)} held-out concepts marked done.",
            "",
            "| Metric | Agreement with gold |",
            "|---|---|",
            *(f"| {m} | {_pct(summary[m])} |" for m in GRADED + REPORTED),
            "",
            "`intent` also accepts the second reading listed in `concepts.ALSO_ACCEPTED`; "
            "`intent_strict` is against the gold intent alone. `spurious_ambiguity` is the share "
            "of clear requests the annotator still asked about (lower means closer to gold); the "
            "other rows are agreement.",
            "",
            "| Concept | Category | intent | ambiguity | interventions | topology | metrics "
            "| arms |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, concept, s in scored:
            lines.append(
                f"| {concept.id} | {concept.category} | {_mark(s.intent)} | "
                f"{_mark(_ambiguity_ok(s))} | "
                f"{_mark(s.interventions)} | {_mark(s.topology_changes)} | "
                f"{_mark(s.metrics_of_interest)} | "
                f"{_mark(s.arm_structure if s.multi_arm else None)} |"
            )
        disagreements = [
            (a, c, s) for a, c, s in scored
            if failed_fields_of(s) or s.spurious_ambiguity
        ]
        if disagreements:
            lines += ["", "### Disagreements", ""]
        for ann, concept, s in disagreements:
            failed = failed_fields_of(s) + (["spurious_ambiguity"] if s.spurious_ambiguity else [])
            lines += [
                f"**{concept.id}** ({concept.category}) — differs on {', '.join(failed)}",
                "",
                f"> {concept.text}",
                "",
                "Gold:",
                *(f"    {line}" for line in _gold_lines(concept)),
                "",
                "Annotator:",
                *(f"    {line}" for line in (
                    describe_question(ann.question) if ann.question else ["(no Question)"]
                )),
                "",
            ]
            if ann.notes:
                lines += [f"Notes: {ann.notes}", ""]
    if len(exports) > 1:
        lines += [
            "## Between annotators",
            "",
            "| Pair | Shared | intent | κ intent | ambiguous? | κ ambiguous | arm structure |",
            "|---|---|---|---|---|---|---|",
        ]
        for a, b in combinations(exports, 2):
            p = pairwise(a, b)
            kappa = lambda k: "—" if k is None else f"{k:.2f}"  # noqa: E731
            lines.append(
                f"| {a.annotator} / {b.annotator} | {p['shared']} | {_pct(p['intent'])} | "
                f"{kappa(p['intent_kappa'])} | {_pct(p['ambiguous'])} | "
                f"{kappa(p['ambiguous_kappa'])} | {_pct(p['arm_structure'])} |"
            )
    return "\n".join(lines) + "\n"


def failed_fields_of(score: RequestScore) -> list[str]:
    """The graded fields a done annotation gets wrong (same rules as the Parser report)."""
    fields = {
        "intent": score.intent,
        "interventions": score.interventions,
        "topology_changes": score.topology_changes,
        "metrics_of_interest": score.metrics_of_interest,
        "ambiguity_detection": score.ambiguity_detected,
        "arm_structure": score.arm_structure if score.multi_arm else None,
    }
    return [name for name, ok in fields.items() if ok is False]


def external_requests(exports: Sequence[Export]) -> list[dict[str, Any]]:
    """The requests annotators wrote, each with its author's annotation as gold."""
    out = []
    for export in exports:
        for item in export.external:
            if not item.get("text") or not item.get("done") or item.get("question") is None:
                continue
            adapter_for(Question).validate_python(item["question"])  # fail early on a bad one
            out.append({
                "id": f"X-{export.annotator}-{item['id']}",
                "author": export.annotator,
                "text": item["text"],
                "question": item["question"],
                "notes": item.get("notes", ""),
            })
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("exports", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, help="write the Markdown report here")
    parser.add_argument("--external-out", type=Path,
                        help="write the annotators' own requests (with their gold) here")
    args = parser.parse_args()
    exports = [load_export(p) for p in args.exports]
    report = render(exports)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"report written to {args.out}")
    else:
        print(report)
    if args.external_out:
        external = external_requests(exports)
        args.external_out.write_text(json.dumps(external, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
        print(f"{len(external)} external requests written to {args.external_out}")


if __name__ == "__main__":
    main()
