"""ADR-0040 decision 6: a use case is a class with an `execute` method.

A module in `application/use_cases/` defines no public top-level function, and every public class
in it has `execute`, except an exception class.
"""

from __future__ import annotations

import ast
from pathlib import Path

USE_CASES = Path(__file__).resolve().parents[2] / "src" / "resto" / "application" / "use_cases"

# Placeholders until E6.1 and E7.1 write them as classes.
PLACEHOLDER_MODULES = {"derive_network", "generate_demand", "generate_network", "reroute_demand"}
# Public functions that are not use cases. `run_ephemeral` stays a function (the r21 spec leaves it
# untouched and only its test calls it); `attempt_dir` is a path helper.
ALLOWED_FUNCTIONS = {"run_ephemeral", "attempt_dir"}


def _is_exception_class(node: ast.ClassDef) -> bool:
    names = [b.id for b in node.bases if isinstance(b, ast.Name)]
    return any(n == "Exception" or n.endswith("Error") for n in names)


def _violations(source: str) -> list[str]:
    """What breaks the convention in one module's source."""
    out: list[str] = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_") and node.name not in ALLOWED_FUNCTIONS:
                out.append(f"public function {node.name}")
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_") or _is_exception_class(node):
                continue
            has_execute = any(
                isinstance(n, ast.FunctionDef) and n.name == "execute" for n in node.body
            )
            if not has_execute:
                out.append(f"class {node.name} has no execute")
    return out


def test_use_case_modules_define_classes_with_execute() -> None:
    found = {
        path.name: problems
        for path in sorted(USE_CASES.glob("*.py"))
        if path.stem not in PLACEHOLDER_MODULES | {"__init__"}
        if (problems := _violations(path.read_text()))
    }
    assert found == {}


def test_a_public_function_is_a_violation() -> None:
    assert _violations("def run_thing(x): ...") == ["public function run_thing"]


def test_a_class_without_execute_is_a_violation() -> None:
    assert _violations("class Thing:\n    def run(self): ...") == ["class Thing has no execute"]


def test_a_class_with_execute_and_private_helpers_is_allowed() -> None:
    source = "class Thing:\n    def execute(self): ...\n\ndef _helper(): ...\nclass _Private: ..."
    assert _violations(source) == []


def test_an_exception_class_is_allowed() -> None:
    assert _violations("class Boom(RuntimeError):\n    pass") == []


def test_the_explicit_function_exclusions_are_allowed() -> None:
    assert _violations("def run_ephemeral(): ...\ndef attempt_dir(): ...") == []
