"""Promoters (ADR-0001, ADR-0042 §5): each one takes an agent run and the context the agent was
given and returns the promoted object, or raises `DraftRejected` (`RunWithoutDraft` when the run
ended without a draft, `resto.application.promotion`). A promoter reads and stores nothing: whoever
called the agent loads what the promoter needs and stores what it returns. Names end in `Promoter`
and the one public method is `promote(run, context)`.

They live outside the study flow so that `eval/` and the use cases import them without it.
`tests/unit/test_import_boundaries.py` fails when a module here imports a repository port or the
study package (`application/run_study/`).
"""
