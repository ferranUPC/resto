"""Import-shape rules from CODING_STANDARDS.md that a scan can enforce.

Layer direction (CLAUDE.md): `domain` <- `application` <- `adapters` / `interface`; `domain` is
stdlib only. `eval/` sits outside the hexagon and may import `resto`, never the reverse. A private
name (`_Foo`) is not imported across modules: if two modules need it, it is not private. An event
handler never imports the study package, `run_study` (ADR-0042 §11). A promoter reads and stores
nothing and stands apart from the study flow (ADR-0042 §5): no module of `application/promoters/`
imports a repository port or the study package.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
FORBIDDEN_FROM_APPLICATION = {"adapters", "interface"}
STUDY_PACKAGES = ("resto.application.run_study",)
PROMOTERS_MAY_NOT_IMPORT = ("resto.application.ports.repositories", *STUDY_PACKAGES)
RULES = ("domain", "application", "eval", "private", "event_handlers", "promoters")


def _imports(tree: ast.AST) -> list[tuple[str, list[str]]]:
    """Absolute imports as (module, imported names); relative imports are skipped."""
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, []) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module, [alias.name for alias in node.names]))
    return found


def _is_private(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


def _is_within(module: str, packages: tuple[str, ...]) -> bool:
    return any(module == p or module.startswith(f"{p}.") for p in packages)


def _violations(root: Path) -> dict[str, list[str]]:
    """Map each rule to the offending `file: import` lines found under `root`/resto."""
    out: dict[str, list[str]] = {rule: [] for rule in RULES}
    for path in sorted((root / "resto").rglob("*.py")):
        parts = path.relative_to(root / "resto").parts
        layer = parts[0]
        in_handlers = parts[:2] == ("application", "event_handlers")
        is_promoter = parts[:2] == ("application", "promoters")
        for module, names in _imports(ast.parse(path.read_text())):
            top, _, rest = module.partition(".")
            second = rest.partition(".")[0]
            where = f"{path.relative_to(root).as_posix()}: {module}"
            if top == "eval":
                out["eval"].append(where)
            if layer == "domain":
                is_resto = top == "resto"
                if (is_resto and second != "domain") or (
                    not is_resto and top not in sys.stdlib_module_names
                ):
                    out["domain"].append(where)
            if layer == "application" and top == "resto" and second in FORBIDDEN_FROM_APPLICATION:
                out["application"].append(where)
            if in_handlers and _is_within(module, STUDY_PACKAGES):
                out["event_handlers"].append(where)
            if is_promoter and _is_within(module, PROMOTERS_MAY_NOT_IMPORT):
                out["promoters"].append(where)
            if top == "resto":
                out["private"].extend(f"{where}.{n}" for n in names if _is_private(n))
    return out


def test_src_follows_layer_direction_and_never_imports_eval() -> None:
    assert _violations(SRC) == {rule: [] for rule in RULES}


def test_scan_flags_each_violation_kind(tmp_path: Path) -> None:
    pkg = tmp_path / "resto"
    (pkg / "domain").mkdir(parents=True)
    (pkg / "application" / "promoters").mkdir(parents=True)
    (pkg / "domain" / "a.py").write_text("import pydantic\nfrom resto.adapters import x\n")
    (pkg / "application" / "b.py").write_text(
        "from resto.interface import y\nimport eval.z\nfrom resto.domain.m import _Hidden\n"
    )
    (pkg / "application" / "event_handlers").mkdir()
    (pkg / "application" / "event_handlers" / "c.py").write_text(
        "from resto.application.run_study.spend import StudySpend\n"
        "from resto.application.run_study import RunStudy\n"
    )
    (pkg / "application" / "promoters" / "d.py").write_text(
        "from resto.application.ports.repositories import NoteRepository\n"
        "from resto.application.run_study.steps import StepContext\n"
        "from resto.application.ports.llm import AgentRun\n"
    )
    found = _violations(tmp_path)
    assert found["domain"] == ["resto/domain/a.py: pydantic", "resto/domain/a.py: resto.adapters"]
    assert found["application"] == ["resto/application/b.py: resto.interface"]
    assert found["eval"] == ["resto/application/b.py: eval.z"]
    assert found["private"] == ["resto/application/b.py: resto.domain.m._Hidden"]
    assert found["event_handlers"] == [
        "resto/application/event_handlers/c.py: resto.application.run_study.spend",
        "resto/application/event_handlers/c.py: resto.application.run_study",
    ]
    assert found["promoters"] == [
        "resto/application/promoters/d.py: resto.application.ports.repositories",
        "resto/application/promoters/d.py: resto.application.run_study.steps",
    ]
