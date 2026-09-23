"""Domain-wide constants."""

SUMO_VERSION = "1.27.1"

DEFAULT_SEEDS = (1, 2, 3)
"""Seeds of a `run_simulation` step that sets none: the scenario matrix's, so studies reuse matrix
results by `result_id` (ADR-0025 §5)."""

DEFAULT_MAX_ROUNDS = 3
"""Expert rounds per free `Study`; the last one is sent in forced mode (ADR-0025 §4)."""

MAX_NOTES_PER_STUDY = 3
"""Notes the Expert may write at the end of a completed study (ADR-0026)."""

DEFAULT_STUDY_MAX_TOKENS = 400_000
"""Input + output tokens all agent calls of one `Study` may spend together, parser included."""

DEFAULT_STUDY_MAX_SIMULATIONS = 30
"""SUMO runs one `Study` may start: 3 phases x 2 arms x `DEFAULT_SEEDS`, with margin."""

DEFAULT_STUDY_MAX_AGENT_CALLS = 20
"""Agent calls of one `Study`: a free GP-8/GP-11 with 3 rounds needs about 18."""

NOTE_VERIFY_LIMIT = 1_000
"""`search_notes` limit when collecting the unverified notes of a scenario to check against a new
result: an empty query scores every note 0.0, so the default limit would silently truncate."""
