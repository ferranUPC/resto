"""Domain-wide constants."""

SUMO_VERSION = "1.27.1"

DEFAULT_SEEDS = (1, 2, 3)
"""Seeds of a `run_simulation` step that sets none: the scenario matrix's, so studies reuse matrix
results by `result_id` (ADR-0025 §5)."""

DEFAULT_MAX_ROUNDS = 3
"""Expert rounds per free `Study`; the last one is sent in forced mode (ADR-0025 §4)."""

MAX_NOTES_PER_STUDY = 3
"""Notes the Expert may write at the end of a completed study (ADR-0026)."""
