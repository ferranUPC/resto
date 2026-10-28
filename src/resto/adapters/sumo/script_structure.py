"""Structure check of a generated `script.py` (ADR-0044): the dry run uses it to confirm the file
has the shape `script_translator` produces, before SUMO runs it."""

from __future__ import annotations

import ast

from resto.adapters.sumo.constants import TRACI_API_MODULE


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
    if not (
        isinstance(first, ast.ImportFrom) and first.module == TRACI_API_MODULE and first.level == 0
    ):
        raise ValueError(f"the only import must be the first statement, from {TRACI_API_MODULE}")

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("start", "close")
        ):
            raise ValueError(f"the script must not call {node.func.id}()")

    last = tree.body[-1]
    if len(tree.body) < 2 or not _is_call(last, ("run",)):
        raise ValueError("the script must end with run()")
    registrations = tree.body[1:-1]
    if len(registrations) != rule_count or not all(
        _is_call(node, ("at_time", "when")) for node in registrations
    ):
        raise ValueError(f"the script needs exactly {rule_count} rule registrations")


def _is_call(node: ast.stmt, names: tuple[str, ...]) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id in names
    )
