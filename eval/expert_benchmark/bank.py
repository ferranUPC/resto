"""Loads `eval/question_bank/question-bank.json` into what the benchmark needs per question: its
family, the `ExpertTask` to run, and the gold answer (docs/evaluating-resto.md §4.1–§4.2)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask

BANK_PATH = Path(__file__).resolve().parents[1] / "question_bank" / "question-bank.json"


class Family(StrEnum):
    DESC_OCC = "desc-occ"
    DESC_TT = "desc-tt"
    DIAG = "diag"
    CF_DIR = "cf-dir"
    CF_TOPK = "cf-topk"
    CF_BAND = "cf-band"

    @classmethod
    def of(cls, question_id: str) -> Family:
        """`S03-desc-occ` -> `DESC_OCC`: the family is the id's suffix after the row label."""
        return cls(question_id.split("-", 1)[1])


@dataclass(frozen=True, slots=True)
class BenchmarkQuestion:
    id: str
    family: Family
    text: str
    network_id: str
    result_ids: tuple[str, ...]
    gold: Mapping[str, Any]

    def to_task(self, mode: Mode = Mode.FORCED) -> ExpertTask:
        return ExpertTask(
            question=self.text,
            mode=mode,
            network_id=self.network_id,
            result_ids=self.result_ids,
            notes_allowed=False,
        )


def _parse(entry: Mapping[str, Any]) -> BenchmarkQuestion:
    baseline = tuple(entry["evidence"].get("baseline_result_ids", ()))
    return BenchmarkQuestion(
        id=entry["id"],
        family=Family.of(entry["id"]),
        text=entry["question"]["text"],
        network_id=entry["question"]["network_ref"],
        result_ids=tuple(entry["result_ids"]) + baseline,
        gold=entry["gold_answer"],
    )


def load_bank(path: Path = BANK_PATH, ids: Iterable[str] | None = None) -> list[BenchmarkQuestion]:
    """The bank in file order, or only `ids` (in the order given).

    Raises:
        KeyError: an id in `ids` is not in the bank.
    """
    questions = [_parse(entry) for entry in json.loads(path.read_text(encoding="utf-8"))]
    if ids is None:
        return questions
    by_id = {q.id: q for q in questions}
    return [by_id[i] for i in ids]
