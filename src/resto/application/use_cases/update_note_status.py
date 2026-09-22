"""A later `SimulationResult` confirms or refutes an `ExpertNote` — deterministic, no LLM call
(ADR-0011: "status that changes only because of a later SimulationResult, never because the agent
revises its own opinion"; DATABASE_MCP_CONTRACT.md: "only code decides that").

First version, deliberately narrow: only network-wide `Quantity` claims (`mean_delay`,
`mean_travel_time`, `teleports`, `departed`, `arrived`) can be checked against a single
`SimulationResult`'s `Kpis` — a direct, single-result comparison with no room for ambiguity.
Per-edge `Quantity`, `Edges` and `Change` claims have no comparison target this simple a check can
derive from one result alone (a `Change` claim needs its own baseline result, which nothing here is
given); a note carrying only those stays `UNVERIFIED` rather than getting a guessed verdict. See
docs/evaluating-resto.md §4.8 and ADR-0024 for the reasoning and where this could be widened.
"""

from __future__ import annotations

from resto.application.ports.repositories import NoteRepository
from resto.domain.entities.expert_note import ExpertNote, NoteStatus
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.services.comparison import within_tolerance
from resto.domain.value_objects.answer_value import Quantity


def update_note_status(
    note: ExpertNote, result: SimulationResult, *, notes: NoteRepository
) -> NoteStatus | None:
    """Checks `note` against `result` and stores the new status if it settles anything.

    Returns the new status, or `None` if `note` was already resolved, is about a different
    scenario, or carries no claim this check can evaluate — left `UNVERIFIED` in every such case.
    """
    if note.status is not NoteStatus.UNVERIFIED or note.scenario_id != result.scenario_id:
        return None
    if result.kpis is None:
        return None
    claims = [v for v in note.values if isinstance(v, Quantity) and v.measure.is_network_wide]
    if not claims:
        return None
    agrees = all(
        within_tolerance(claim.value, getattr(result.kpis, claim.measure.value))
        for claim in claims
    )
    status = NoteStatus.CONFIRMED if agrees else NoteStatus.REFUTED
    notes.update_status(note.note_id, status)
    return status
