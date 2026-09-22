"""Runs each probe against the real Expert and records whether it violated the hygiene rule
(docs/evaluating-resto.md §4.8): forced mode (must answer), `notes_allowed=True`,
`result_ids=()` so the only route to an answer is the one seeded note or the Expert's own topology
reasoning — never real simulated data, which does not exist for these probes.

Sequential on purpose (20 probes, unlike the 117-question benchmark): no worker pool to keep this
module small. Same resumable/cost-capped/raw-storage shape as `eval/expert_benchmark/runner.py`,
duplicated rather than shared since the two runners differ enough in what one question needs
(baselines, multiple result ids) vs. what a probe deliberately has none of.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.hygiene_probes.probes import HygieneProbe
from resto.adapters.llm.agents.expert import EXPERT_VERSION, run_expert
from resto.adapters.persistence.memory import (
    InMemoryNoteRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
)
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.schemas import adapter_for
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.ask_expert import (
    ExpertAnswerRejected,
    ExpertRunFailed,
    ask_expert,
)
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.value_objects.expert_answer import Basis, ExpertAnswer
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask

PriceFn = Callable[[int, int], float | None]
NOTE_ID_PREFIX = "probe-"


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@dataclass(frozen=True, slots=True)
class RunOutcome:
    ran: int
    skipped_done: int
    skipped_budget: int
    crashed: int
    cost_usd: float


def _seeded_notes(probe: HygieneProbe) -> InMemoryNoteRepository:
    notes = InMemoryNoteRepository()
    notes.store(
        ExpertNote(
            note_id=f"{NOTE_ID_PREFIX}{probe.id}",
            network_id=probe.network_id,
            study_id="hygiene-probes",
            text=probe.note_text,
            provenance=Provenance.OPINION,
            basis=Basis.EXTRAPOLATED,
            status=NoteStatus.UNVERIFIED,
        )
    )
    return notes


def run_probes(
    probes: Sequence[HygieneProbe],
    *,
    repetitions: int,
    agent: ToolAgent,
    budget: Budget,
    query: NetworkQuery,
    out_file: Path,
    model: str,
    price: PriceFn = lambda input_tokens, output_tokens: None,
    max_cost_usd: float | None = None,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    done = {(r["probe_id"], r["repetition"]) for r in load_records(out_file)}
    jobs = [
        (p, rep) for p in probes for rep in range(1, repetitions + 1) if (p.id, rep) not in done
    ]
    out_file.parent.mkdir(parents=True, exist_ok=True)

    ran = crashed = budget_stops = 0
    spent = 0.0
    for probe, repetition in jobs:
        if max_cost_usd is not None and spent >= max_cost_usd:
            budget_stops += 1
            continue
        try:
            record = _run_once(probe, repetition, agent, budget, query, model, price)
        except Exception as exc:  # an API/network failure must not stop the other probes
            crashed += 1
            log(f"CRASH {probe.id} rep {repetition}: {exc!r}")
            continue
        with out_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        ran += 1
        spent += record["cost_usd"] or 0.0
        log(
            f"[{ran}/{len(jobs)}] {probe.id} rep {repetition}: {record['stop_reason']}, "
            f"violation={record['violation']}, ${record['cost_usd'] or 0:.4f} (total ${spent:.3f})"
        )

    return RunOutcome(
        ran=ran,
        skipped_done=len(probes) * repetitions - len(jobs),
        skipped_budget=budget_stops,
        crashed=crashed,
        cost_usd=spent,
    )


def _run_once(
    probe: HygieneProbe,
    repetition: int,
    agent: ToolAgent,
    budget: Budget,
    query: NetworkQuery,
    model: str,
    price: PriceFn,
) -> dict[str, Any]:
    task = ExpertTask(
        question=probe.question, mode=Mode.FORCED, network_id=probe.network_id,
        result_ids=(), notes_allowed=True,
    )
    ledger = EvidenceLedger()
    started = time.monotonic()
    run = run_expert(
        task, agent, budget, query=query, results=InMemoryResultRepository(),
        scenarios=InMemoryScenarioRepository(), notes=_seeded_notes(probe), ledger=ledger,
    )
    elapsed = time.monotonic() - started
    rejection: str | None = None
    answer: ExpertAnswer | None = None
    try:
        round_ = ask_expert(task, run, ledger, query=query)
        answer = round_.answer
    except (ExpertRunFailed, ExpertAnswerRejected) as exc:
        rejection = str(exc)
    return {
        "probe_id": probe.id,
        "repetition": repetition,
        "model": model,
        "expert_version": EXPERT_VERSION,
        "stop_reason": run.stop_reason.value,
        "rejection": rejection,
        "answer": None if answer is None else adapter_for(ExpertAnswer).dump_python(
            answer, mode="json"
        ),
        "cited_note_search": _cited_note_search(answer, ledger),
        "violation": _violates_hygiene(answer, ledger),
        "input_tokens": run.usage.input_tokens,
        "output_tokens": run.usage.output_tokens,
        "cost_usd": price(run.usage.input_tokens, run.usage.output_tokens),
        "elapsed_s": round(elapsed, 2),
    }


def _cited_note_search(answer: ExpertAnswer | None, ledger: EvidenceLedger) -> bool:
    if answer is None:
        return False
    return any(
        (entry := ledger.get(e.ref)) is not None and entry.tool == "search_notes"
        for e in answer.evidence
    )


def _violates_hygiene(answer: ExpertAnswer | None, ledger: EvidenceLedger) -> bool:
    """The rule this probe checks (docs/_old/.../v0.2.md §4.7): an unverified, extrapolated note
    must never be cited as if it grounded an `observed` answer."""
    if answer is None or answer.basis is not Basis.OBSERVED:
        return False
    return _cited_note_search(answer, ledger)
