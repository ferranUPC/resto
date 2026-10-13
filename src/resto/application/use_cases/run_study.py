"""`RunStudy`: user text -> a closed `Study`. Parses the text into a `Question` and hands it to
the Executor (`application/executor/`), which does the rest."""

from __future__ import annotations

from dataclasses import dataclass, replace

from resto.application.executor import StudyDeps, StudySettings, execute_study
from resto.application.ports.llm import StopReason
from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.entities.study import Study
from resto.domain.value_objects.question import Mode


class ParserFailed(RuntimeError):
    """The Input Parser produced no valid `Question`: no `Study` exists (ADR-0025 §3), the CLI
    reports the error."""


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
        given, is the user's choice and overrides the parser's.

        Raises:
            ParserFailed: no valid `Question`, so no `Study` was created.
        """
        try:
            run = self.deps.agents.parser.parse(text)
        except Exception as e:
            raise ParserFailed(f"the Input Parser failed: {type(e).__name__}: {e}") from e
        if run.stop_reason is not StopReason.OUTPUT or run.output is None:
            raise ParserFailed(f"the Input Parser stopped on {run.stop_reason} without a Question")
        question = run.output if mode is None else replace(run.output, mode=mode)
        return execute_study(question, run.usage, self.deps, self.settings, max_rounds=max_rounds)
