"""Contracts the `agentic` setup reuses unchanged: its protocol and the data-only golden paths."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from golden.framework import GoldenPath, Run
from golden.paths import discover
from golden.setups.agentic import AgenticSetup
from golden.setups.fake import FakeSetup

from resto.domain.entities.study import Study
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import StepRecord
from resto.domain.value_objects.study_plan import StudyPlan


class _Stub:
    repetitions = 1
    compare_repetitions = False
    models: Mapping[str, str] = {"expert": "m"}

    def estimate_cost(self, paths: tuple[GoldenPath, ...]) -> Decimal:
        return Decimal(0)

    def run(self, path: GoldenPath) -> Run:
        raise NotImplementedError


def test_an_object_with_the_agentic_members_is_an_agentic_setup() -> None:
    assert isinstance(_Stub(), AgenticSetup)


def test_an_object_without_a_cost_estimate_is_not_an_agentic_setup() -> None:
    class NoEstimate:
        repetitions = 1
        compare_repetitions = False
        models: Mapping[str, str] = {}

        def run(self, path: GoldenPath) -> Run:
            raise NotImplementedError

    assert not isinstance(NoEstimate(), AgenticSetup)


def test_the_fake_setup_is_not_an_agentic_setup() -> None:
    assert not isinstance(FakeSetup({}), AgenticSetup)


_AGENT_OUTPUT = (Question, StudyPlan, ExpertAnswer, StepRecord, Study)


def _values(value: Any) -> Iterator[Any]:
    yield value
    if is_dataclass(value) and not isinstance(value, type):
        for f in fields(value):
            yield from _values(getattr(value, f.name))
    elif isinstance(value, tuple | list | set | frozenset):
        for item in value:
            yield from _values(item)
    elif isinstance(value, dict):
        for item in (*value.keys(), *value.values()):
            yield from _values(item)


def test_no_golden_path_holds_agent_output() -> None:
    for path in discover():
        for value in _values(path):
            assert not isinstance(value, _AGENT_OUTPUT), f"{path.name} holds {type(value)}"


def test_golden_path_data_is_plain_values_and_stored_facts() -> None:
    for path in discover():
        for value in _values(path):
            module = type(value).__module__
            assert (
                value is None
                or (
                    isinstance(value, type)
                    and value.__module__ == "resto.application.ports.tracing"
                )
                or isinstance(value, str | int | float | bool | Enum | tuple | dict)
                or module.startswith("golden.framework")
                or module.startswith("resto.domain.value_objects.")
            ), f"{path.name} holds {type(value)}"
