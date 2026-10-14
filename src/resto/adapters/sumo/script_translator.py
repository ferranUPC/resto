"""Translator from a `TraciScript` to the Python source of `script.py` (ADR-0044).

Pure text, no SUMO. The output is one `from resto.traci_api import ...` line, one `at_time(...)` or
`when(...)` per rule in rule order, and `run()` last. The same script gives the same bytes. The file
never calls `start` or `close`: the harness around it does.

Each trigger and action variant has a small class here that renders its own call under the same
method name, `render`; the domain types stay free of Python text (ADR-0044 decision 3).
`script_structure` checks that a generated file has the shape this module produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from resto.adapters.sumo.constants import TRACI_API_MODULE
from resto.domain.value_objects.condition import Metric
from resto.domain.value_objects.traci_script import (
    AtTime,
    CloseLane,
    OpenLane,
    SetSpeed,
    SetTlsProgram,
    TraciScript,
    When,
)


@dataclass(frozen=True)
class CloseLaneCall:
    action: CloseLane
    functions: ClassVar[tuple[str, ...]] = ("close_lane",)

    def render(self) -> str:
        return f"close_lane({self.action.lane_id!r})"


@dataclass(frozen=True)
class OpenLaneCall:
    action: OpenLane
    functions: ClassVar[tuple[str, ...]] = ("open_lane",)

    def render(self) -> str:
        return f"open_lane({self.action.lane_id!r})"


@dataclass(frozen=True)
class SetSpeedCall:
    action: SetSpeed
    functions: ClassVar[tuple[str, ...]] = ("set_speed",)

    def render(self) -> str:
        return f"set_speed({self.action.edge_id!r}, {float(self.action.speed)!r})"


@dataclass(frozen=True)
class SetTlsProgramCall:
    action: SetTlsProgram
    functions: ClassVar[tuple[str, ...]] = ("set_tls_program",)

    def render(self) -> str:
        return f"set_tls_program({self.action.tls_id!r}, {self.action.program_id!r})"


@dataclass(frozen=True)
class AtTimeCall:
    trigger: AtTime
    functions: ClassVar[tuple[str, ...]] = ("at_time",)

    def render(self, action: str) -> str:
        return f"at_time({float(self.trigger.t)!r}, lambda: {action})"


@dataclass(frozen=True)
class WhenCall:
    trigger: When
    metric_functions: ClassVar[dict[Metric, str]] = {
        Metric.OCCUPANCY: "get_edge_occupancy",
        Metric.SPEED: "get_edge_speed",
        Metric.VEHICLE_COUNT: "get_vehicle_count",
    }

    @property
    def functions(self) -> tuple[str, ...]:
        return ("when", self.metric_functions[self.trigger.condition.metric])

    def render(self, action: str) -> str:
        condition = self.trigger.condition
        function = self.metric_functions[condition.metric]
        return (
            f"when(lambda: {function}({condition.target!r}) {condition.op.value} "
            f"{float(condition.value)!r}, lambda: {action})"
        )


# One lookup per variant family; a variant without an entry fails with a KeyError.
_ACTION_CALLS: dict[type, Any] = {
    CloseLane: CloseLaneCall,
    OpenLane: OpenLaneCall,
    SetSpeed: SetSpeedCall,
    SetTlsProgram: SetTlsProgramCall,
}
_TRIGGER_CALLS: dict[type, Any] = {AtTime: AtTimeCall, When: WhenCall}


def translate_script(script: TraciScript) -> str:
    used = {"run"}
    lines = []
    for rule in script.rules:
        action = _ACTION_CALLS[type(rule.action)](rule.action)
        trigger = _TRIGGER_CALLS[type(rule.trigger)](rule.trigger)
        used.update(action.functions, trigger.functions)
        lines.append(trigger.render(action.render()))
    header = f"from {TRACI_API_MODULE} import {', '.join(sorted(used))}"
    return "\n".join([header, "", *lines, "run()"]) + "\n"
