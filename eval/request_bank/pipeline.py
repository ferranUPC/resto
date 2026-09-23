"""Variant generation for the request bank: generator rewrite → code noise → back-translation →
verifier check. The LLM is injected (`Chat`) so the logic is tested without the API."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from eval.request_bank.concepts import LANGUAGES, Concept, Noise, Style, Vague, VariantSpec
from eval.request_bank.noise import add_typos, strip_accents

PROMPT_VERSION = "v2"


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    cost_usd: float = 0.0


class Chat(Protocol):
    def __call__(self, model: str, system: str, user: str) -> Reply: ...


@dataclass(frozen=True, slots=True)
class Models:
    generator: str
    verifier: str


@dataclass(frozen=True, slots=True)
class VariantRecord:
    id: str
    concept_id: str
    lang: str
    style: str | None
    vague: str | None
    noise: str | None
    text: str
    generated: str | None
    back_translation: str | None
    verified: bool
    differences: tuple[str, ...] = ()
    generator: str | None = None
    verifier: str | None = None
    prompt_version: str = PROMPT_VERSION
    cost_usd: float = 0.0
    notes: tuple[str, ...] = ()
    verifier_output: str | None = None


_GENERATOR_SYSTEM = (
    "You rewrite requests that a user sends to a traffic-simulation assistant, to build a test "
    "set. Always write as that user, addressing the assistant: never write as the assistant, "
    "never ask anyone for a request. Output only the rewritten request: no quotes, no preamble, "
    "no explanation."
)

_TRANSLATOR_SYSTEM = "You translate text. Output only the translation."

_STYLE = {
    Style.TECHNICAL: "Write it as a traffic engineer would: terse and technical.",
    Style.COLLOQUIAL: "Write it casually, as a non-expert would type it in a chat.",
    Style.TELEGRAPHIC: (
        "Write it in telegraphic style: as few words as possible, no full sentences."
    ),
    Style.VERBOSE: (
        "Write it as a long message with some irrelevant context around the request (who you "
        "are, why you ask); the request itself must stay complete."
    ),
    Style.MESSY: (
        "Write it as a hurried message: poor punctuation, abbreviations, run-on sentences. It "
        "should be hard to read, but a careful reader must still find every piece of information."
    ),
}

_EXACT = (
    "Keep exactly the same meaning: every network or place, edge, lane, time, value and every "
    "requested measure must still be recoverable without guessing, and changes that are compared "
    "must stay compared while changes applied together stay together. Do not add information. "
    "You may express times, numbers, units and places in any natural way a person would (for "
    "example '8 in the morning', 'the street from B0 to C0', '8.3 m/s')."
)

_VAGUE = {
    Vague.TIME: (
        "Make the time imprecise, as someone not looking at a clock would say it (for example "
        "'early in the morning', 'for a while'): the exact start and end must no longer be "
        "recoverable."
    ),
    Vague.VALUE: (
        "Make the numeric value(s) imprecise (for example 'much slower', 'a bit more traffic'): "
        "the exact amount must no longer be recoverable."
    ),
    Vague.PLACE: (
        "Refer to the place(s) vaguely (for example 'the main street', 'that busy road'), so the "
        "exact edge or lane can no longer be identified."
    ),
    Vague.GROUPING: (
        "Phrase it so that it is unclear whether the changes are meant to be applied together or "
        "compared against each other: just mention the changes one after the other, and do not "
        "use any word that settles it, such as 'or', 'versus', 'compare', 'which is better', "
        "'together', 'at the same time', 'both' or 'each'."
    ),
}

_VAGUE_ASPECT = {
    Vague.TIME: "the time (its start and end)",
    Vague.VALUE: "the numeric value(s)",
    Vague.PLACE: "the place (which edge or lane)",
    Vague.GROUPING: "whether the changes are applied together or compared",
}

_VERIFIER_SYSTEM = (
    "You check test data for a traffic-simulation assistant. Answer only with a JSON object."
)

_COMPARED = (
    "the network or place; every edge, lane and junction; every time and duration; every "
    "numeric value (a unit conversion is fine if the value is equivalent); whether several "
    "changes are applied together or compared; which measures are asked for; what kind of "
    "question it is. Ignore style, register, spelling and language."
)


def rewrite_prompt(base: str, spec: VariantSpec) -> str:
    lines = [
        f"Write it in {LANGUAGES[spec.lang]}." if spec.lang != "en" else "Keep it in English."
    ]
    if spec.style is not None:
        lines.append(_STYLE[spec.style])
    if spec.vague is not None:
        lines.append(_VAGUE[spec.vague] + " Keep everything else exactly as it is.")
    else:
        lines.append(_EXACT)
    return "Rewrite this request.\n" + "\n".join(lines) + f"\n\nRequest:\n{base}"


def back_translation_prompt(text: str) -> str:
    return (
        "Translate this request into English as literally as possible, keeping every detail "
        f"and any vagueness. Output only the translation.\n\n{text}"
    )


def verify_prompt(
    base: str, variant: str, spec: VariantSpec, back_translation: str | None = None
) -> str:
    head = "Request A is the original. Request B was rewritten from it"
    head += f" in {LANGUAGES[spec.lang]}" if spec.lang != "en" else ""
    head += f".\n\nA: {base}\nB: {variant}\n"
    if back_translation:
        head += (
            f"(An English translation of B, for reference only; it may be imperfect: "
            f"{back_translation})\n"
        )
    head += (
        "\nB being in another language, register or spelling is expected and is NOT a "
        "difference. Also check that B is written as a user making a request to the assistant, "
        "not as the assistant.\n"
    )
    if spec.vague is None:
        return head + (
            f"Does B ask for exactly the same thing as A? Compare: {_COMPARED}\n"
            'Answer only with JSON: {"is_user_request": true or false, "same_meaning": true or '
            'false, "differences": ["..."]}.'
        )
    aspect = _VAGUE_ASPECT[spec.vague]
    return head + (
        f"B should mean the same as A except that {aspect} was made vague. Check (1) whether "
        f"{aspect} in B is vague, i.e. a careful reader can NOT determine it exactly, and (2) "
        f"whether everything else is the same as A. Compare: {_COMPARED}\n"
        'Answer only with JSON: {"is_user_request": true or false, "target_is_vague": true or '
        'false, "rest_same": true or false, "differences": ["..."]}.'
    )


def _json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    raw = match.group(0)
    for candidate in (raw, re.sub(r"\bTrue\b", "true", re.sub(r"\bFalse\b", "false", raw))):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def parse_verdict(text: str, spec: VariantSpec) -> tuple[bool, tuple[str, ...]]:
    data = _json_object(text)
    if data is None:
        return False, ("unparseable verifier output",)
    differences = tuple(str(d) for d in data.get("differences") or ())
    if data.get("is_user_request") is False:
        differences = ("not written as a user request", *differences)
    user_ok = data.get("is_user_request", True) is True
    if spec.vague is None:
        return user_ok and data.get("same_meaning") is True, differences
    ok = user_ok and data.get("target_is_vague") is True and data.get("rest_same") is True
    if data.get("target_is_vague") is not True:
        differences = (f"{_VAGUE_ASPECT[spec.vague]} is still precise", *differences)
    return ok, differences


def _same_text(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def apply_noise(text: str, spec: VariantSpec, seed: str) -> str:
    if spec.noise is Noise.TYPOS:
        return add_typos(text, seed)
    if spec.noise is Noise.NO_ACCENTS:
        return strip_accents(text)
    return text


def _record(concept: Concept, spec: VariantSpec, **rest: Any) -> VariantRecord:
    return VariantRecord(
        id=concept.variant_id(spec), concept_id=concept.id, lang=spec.lang,
        style=spec.style, vague=spec.vague, noise=spec.noise, **rest,
    )


def generate_variant(
    concept: Concept, spec: VariantSpec, chat: Chat, models: Models
) -> VariantRecord:
    variant_id = concept.variant_id(spec)
    if not spec.needs_llm:
        return _record(
            concept, spec, text=apply_noise(concept.text, spec, variant_id), generated=None,
            back_translation=None, verified=True, notes=("code noise only",),
        )

    cost = 0.0
    generated = chat(models.generator, _GENERATOR_SYSTEM, rewrite_prompt(concept.text, spec))
    cost += generated.cost_usd
    rewritten = generated.text.strip()

    back = None
    if spec.lang != "en":
        reply = chat(models.generator, _TRANSLATOR_SYSTEM, back_translation_prompt(rewritten))
        cost += reply.cost_usd
        back = reply.text.strip()

    verdict = chat(
        models.verifier, _VERIFIER_SYSTEM, verify_prompt(concept.text, rewritten, spec, back)
    )
    cost += verdict.cost_usd
    verified, differences = parse_verdict(verdict.text, spec)
    if _same_text(rewritten, concept.text):
        verified, differences = False, ("the variant is the original text", *differences)

    return _record(
        concept,
        spec,
        text=apply_noise(rewritten, spec, variant_id),
        generated=rewritten,
        back_translation=back,
        verified=verified,
        differences=differences,
        generator=models.generator,
        verifier=models.verifier,
        cost_usd=round(cost, 6),
        verifier_output=verdict.text,
    )
