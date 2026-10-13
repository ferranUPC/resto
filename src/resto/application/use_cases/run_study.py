"""`RunStudy`: user text -> a closed `Study`. The study is created at the request and the Executor
(`application/executor/`) runs it, the Input Parser being its first stage (ADR-0041 §7)."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.executor import StudyDeps, StudySettings, execute_study
from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.entities.study import Study
from resto.domain.value_objects.question import Mode


@dataclass(frozen=True, slots=True)
class RunStudy:
    """Runs the user's request to a closed `Study`. `deps` holds the collaborators and every
    intermediate state goes to `deps.studies`; `settings` is what varies per run."""

    deps: StudyDeps
    settings: StudySettings

    def execute(
        self, text: str, *, mode: Mode | None = None, max_rounds: int = DEFAULT_MAX_ROUNDS
    ) -> Study:
        """Returns the closed `Study` (`completed`, `failed` or `awaiting_user`). `mode`, when
        given, is the user's choice and overrides the parser's. A request the Input Parser cannot
        turn into a `Question` is a study `failed` at `parsing`."""
        return execute_study(text, mode, self.deps, self.settings, max_rounds=max_rounds)
