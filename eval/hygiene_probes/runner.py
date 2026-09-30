"""Runs each probe against the real Expert and records whether it violated the hygiene rule
(docs/evaluating-resto.md §4.8): forced mode (must answer), `notes_allowed=True`,
`result_ids=()` so the only route to an answer is the one seeded note or the Expert's own topology
reasoning — never real simulated data, which does not exist for these probes.

Resume, the cost policy and the worker pool live in `eval.paid_runs.run_paid_jobs`
(refactor-paid-runs, ticket 04); this module supplies only the job, its resume key, and how to run
one (`_run_once`).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from eval.fixed_network_query_loader import FixedNetworkQueryLoader
from eval.hygiene_probes.probes import HygieneProbe
from eval.paid_runs import ESTIMATED_COST_KEY, REAL_COST_KEY, CostPolicy, RunOutcome, run_paid_jobs
from resto.adapters.llm.agents.expert import EXPERT_VERSION, run_expert
from resto.adapters.persistence.memory import (
    InMemoryNoteRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
)
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.schemas import adapter_for
from resto.application.tools.expert import EvidenceLedger, expert_context
from resto.application.use_cases.ask_expert import (
    ExpertAnswerRejected,
    ExpertRunFailed,
    ask_expert,
)
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.value_objects.expert_answer import Basis, ExpertAnswer
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask

NOTE_ID_PREFIX = "probe-"

Job = tuple[HygieneProbe, int]
NetworkQueryFactory = Callable[[], NetworkQuery]


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


def _key(job: Job) -> tuple[str, int]:
    probe, repetition = job
    return (probe.id, repetition)


def _record_key(record: dict[str, Any]) -> tuple[str, int]:
    return (record["probe_id"], record["repetition"])


def run_probes(
    probes: Sequence[HygieneProbe],
    *,
    repetitions: int,
    agent: ToolAgent,
    budget: Budget,
    query: NetworkQueryFactory,
    out_file: Path,
    cost_policy: CostPolicy,
    workers: int = 1,
    log: Callable[[str], None] = print,
) -> RunOutcome:
    """`query` is a factory, not a shared instance: a `SumolibNetworkQuery` wraps sumolib state
    (e.g. `getShortestPath`) that is not safe to call from more than one thread at once, so each
    worker thread gets its own (`eval/expert_benchmark/runner.py`'s `Environment` has the same
    rule, for the same reason plus its SQLite connection)."""
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    jobs: list[Job] = [(p, rep) for p in probes for rep in range(1, repetitions + 1)]
    local = threading.local()

    def thread_query() -> NetworkQuery:
        if not hasattr(local, "query"):
            local.query = query()
        return local.query  # type: ignore[no-any-return]

    def run_one(job: Job) -> dict[str, Any]:
        probe, repetition = job
        return _run_once(probe, repetition, agent, budget, thread_query(), cost_policy)

    return run_paid_jobs(
        jobs,
        run_one=run_one,
        key=_key,
        record_key=_record_key,
        cost_policy=cost_policy,
        out_file=out_file,
        workers=workers,
        log=log,
    )


def _run_once(
    probe: HygieneProbe,
    repetition: int,
    agent: ToolAgent,
    budget: Budget,
    query: NetworkQuery,
    cost_policy: CostPolicy,
) -> dict[str, Any]:
    task = ExpertTask(
        question=probe.question, mode=Mode.FORCED, network_id=probe.network_id,
        result_ids=(), notes_allowed=True,
    )
    ledger = EvidenceLedger()
    started = time.monotonic()
    context = expert_context(
        task, query=query, results=InMemoryResultRepository(),
        scenarios=InMemoryScenarioRepository(), notes=_seeded_notes(probe),
    )
    run = run_expert(task, agent, budget, context, ledger)
    elapsed = time.monotonic() - started
    rejection: str | None = None
    answer: ExpertAnswer | None = None
    try:
        round_ = ask_expert(task, run, ledger, loader=FixedNetworkQueryLoader(query))
        answer = round_.answer
    except (ExpertRunFailed, ExpertAnswerRejected) as exc:
        rejection = str(exc)
    return {
        "probe_id": probe.id,
        "repetition": repetition,
        "model": cost_policy.model,
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
        ESTIMATED_COST_KEY: cost_policy.price(run.usage.input_tokens, run.usage.output_tokens),
        REAL_COST_KEY: run.usage.cost_usd,
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
