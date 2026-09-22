"""Pure numeric comparison shared by anything that scores a predicted value against a measured
one — the Expert benchmark (`eval/expert_benchmark/scoring.py`) and, since it needs the exact same
rule to confirm/refute an `ExpertNote` (E4.6), `application/use_cases/update_note_status.py` too.
Kept domain-pure (stdlib only) so both `eval/` and `application/` can import it without breaking
the dependency direction `eval/` -> `application/`/`domain/`, never the reverse."""

from __future__ import annotations

NUMERIC_TOLERANCE = 0.05


def within_tolerance(predicted: float, gold: float, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    if gold == 0.0:
        return predicted == 0.0
    return abs(predicted - gold) <= tolerance * abs(gold)
