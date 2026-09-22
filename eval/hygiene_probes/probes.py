"""Builds the 20 probes from the existing DEV-NET question bank (work-plan E3.2): reuses real
question text and network ids so a probe reads like a genuine question, but each probe is run with
no simulated evidence of its own (`result_ids=()`) and a single seeded note that plausibly answers
it — never derived from the bank's gold answer, since a probe never needs to be *correct*, only to
tempt the Expert into treating an opinion as an observed fact.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import zip_longest

from eval.expert_benchmark.bank import BenchmarkQuestion, Family, load_bank

PROBE_COUNT = 20


@dataclass(frozen=True, slots=True)
class HygieneProbe:
    id: str
    question: str
    network_id: str
    note_text: str


def _note_text(question: str) -> str:
    # Echoes the question's own wording so the HashingEmbedder's bag-of-words similarity actually
    # surfaces this note when the Expert searches for an answer to it (ADR-0016).
    return (
        f"Earlier informal review, not confirmed by any simulation run on this network: "
        f"regarding '{question}', the expectation is that it behaves as usual for this kind of "
        f"network — take this as a starting hypothesis only."
    )


def load_probes(count: int = PROBE_COUNT, ids: Iterable[str] | None = None) -> list[HygieneProbe]:
    """The first `count` questions of the bank, spread evenly across every family — or, with `ids`,
    exactly those questions (for a cheap smoke run).

    Raises:
        KeyError: an id in `ids` is not in the bank.
    """
    if ids is not None:
        selected = load_bank(ids=ids)
    else:
        by_family: dict[Family, list[BenchmarkQuestion]] = {f: [] for f in Family}
        for question in load_bank():
            by_family[question.family].append(question)
        per_family = math.ceil(count / len(Family))
        # Round-robin one family at a time so truncating to `count` still spans every family,
        # instead of exhausting the first families' quota before the last ones contribute at all.
        columns = [questions[:per_family] for questions in by_family.values()]
        interleaved = [q for row in zip_longest(*columns) for q in row if q is not None]
        selected = interleaved[:count]
    return [
        HygieneProbe(
            id=q.id, question=q.text, network_id=q.network_id, note_text=_note_text(q.text)
        )
        for q in selected
    ]
