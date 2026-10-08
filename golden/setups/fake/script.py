"""What the scripted agents of one golden path say, in call order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from resto.domain.value_objects.question import Question


@dataclass(frozen=True)
class AgentScript:
    """The `World` arguments that script its agents. An empty slot keeps the World default.

    `plans` are the `StudyPlan`s of the injected planner, one per phase; `expert` holds the
    Expert's answers, one per round (`answers` and `abstains` in the World module build them).
    """

    question: Question | None = None
    plans: tuple[Any, ...] = ()
    expert: tuple[Any, ...] = ()
    builder: tuple[Any, ...] = ()
    author: tuple[Any, ...] = ()
    generator: tuple[Any, ...] = ()
    note_writer: tuple[Any, ...] = ()
    composer: tuple[Any, ...] = ()

    def world_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "plans": self.plans,
            "expert": self.expert,
            "builder": self.builder,
            "author": self.author,
            "generator": self.generator,
            "note_writer": self.note_writer,
            "composer": self.composer,
        }
        if self.question is not None:
            args["question"] = self.question
        return args
