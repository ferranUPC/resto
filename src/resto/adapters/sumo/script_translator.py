"""Translator from a `TraciScript` to the Python source of `script.py` (ADR-0044).

Pure text, no SUMO. The output is one `from resto.traci_api import ...` line, one `at_time(...)` or
`when(...)` per rule in rule order, and `run()` last. The same script gives the same bytes. The file
never calls `start` or `close`: the harness around it does. `check_script_structure` is what the dry
run uses to confirm a generated file has that shape.
"""

from __future__ import annotations

import ast

from resto.domain.value_objects.condition import Condition, Metric
from resto.domain.value_objects.traci_script import (
    Action,
    AtTime,
    CloseLane,
    OpenLane,
    Rule,
    SetSpeed,
    SetTlsProgram,
    TraciScript,
)

_MODULE = "resto.traci_api"
_METRIC_FUNCTIONS = {
    Metric.OCCUPANCY: "get_edge_occupancy",
    Metric.SPEED: "get_edge_speed",
    Metric.VEHICLE_COUNT: "get_vehicle_count",
}
_REGISTRATIONS = ("at_time", "when")
_FORBIDDEN_CALLS = ("start", "close")


def translate_script(script: TraciScript) -> str:
    used: set[str] = {"run"}
    lines = [_rule_line(rule, used) for rule in script.rules]
    header = f"from {_MODULE} import {', '.join(sorted(used))}"
    return "\n".join([header, "", *lines, "run()"]) + "\n"


def _rule_line(rule: Rule, used: set[str]) -> str:
    action = _action_call(rule.action, used)
    trigger = rule.trigger
    if isinstance(trigger, AtTime):
        used.add("at_time")
        return f"at_time({float(trigger.t)!r}, lambda: {action})"
    used.add("when")
    return f"when(lambda: {_condition_expression(trigger.condition, used)}, lambda: {action})"


def _condition_expression(condition: Condition, used: set[str]) -> str:
    function = _METRIC_FUNCTIONS[condition.metric]
    used.add(function)
    return f"{function}({condition.target!r}) {condition.op.value} {float(condition.value)!r}"


def _action_call(action: Action, used: set[str]) -> str:
    match action:
        case CloseLane():
            used.add("close_lane")
            return f"close_lane({action.lane_id!r})"
        case OpenLane():
            used.add("open_lane")
            return f"open_lane({action.lane_id!r})"
        case SetSpeed():
            used.add("set_speed")
            return f"set_speed({action.edge_id!r}, {float(action.speed)!r})"
        case SetTlsProgram():
            used.add("set_tls_program")
            return f"set_tls_program({action.tls_id!r}, {action.program_id!r})"


def check_script_structure(source: str, rule_count: int) -> None:
    """Raises `ValueError` naming the first broken rule: the text parses, has one import from
    `resto.traci_api`, `rule_count` registrations, ends with `run()` and never calls `start` or
    `close`."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ValueError(f"the script does not parse: {error}") from error

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
    if len(imports) != 1:
        raise ValueError(f"the script needs exactly one import, found {len(imports)}")
    first = tree.body[0]
    if not (isinstance(first, ast.ImportFrom) and first.module == _MODULE and first.level == 0):
        raise ValueError(f"the only import must be the first statement, from {_MODULE}")

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_CALLS
        ):
            raise ValueError(f"the script must not call {node.func.id}()")

    last = tree.body[-1]
    if len(tree.body) < 2 or not _is_call(last, ("run",)):
        raise ValueError("the script must end with run()")
    registrations = tree.body[1:-1]
    if len(registrations) != rule_count or not all(
        _is_call(node, _REGISTRATIONS) for node in registrations
    ):
        raise ValueError(f"the script needs exactly {rule_count} rule registrations")


def _is_call(node: ast.stmt, names: tuple[str, ...]) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id in names
    )
