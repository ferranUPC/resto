"""Import-shape rules from CODING_STANDARDS.md that a scan can enforce.

Layer direction (CLAUDE.md): `domain` <- `application` <- `adapters` / `interface`; `domain` is
stdlib only. `eval/` sits outside the hexagon and may import `resto`, never the reverse. A private
name (`_Foo`) is not imported across modules: if two modules need it, it is not private.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
FORBIDDEN_FROM_APPLICATION = {"adapters", "interface"}
RULES = ("domain", "application", "eval", "private")


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


def _violations(root: Path) -> dict[str, list[str]]:
    """Map each rule to the offending `file: import` lines found under `root`/resto."""
    out: dict[str, list[str]] = {rule: [] for rule in RULES}
    for path in sorted((root / "resto").rglob("*.py")):
        layer = path.relative_to(root / "resto").parts[0]
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
            if top == "resto":
                out["private"].extend(f"{where}.{n}" for n in names if _is_private(n))
    return out


def test_src_follows_layer_direction_and_never_imports_eval() -> None:
    assert _violations(SRC) == {rule: [] for rule in RULES}


def test_scan_flags_each_violation_kind(tmp_path: Path) -> None:
    pkg = tmp_path / "resto"
    (pkg / "domain").mkdir(parents=True)
    (pkg / "application").mkdir()
    (pkg / "domain" / "a.py").write_text("import pydantic\nfrom resto.adapters import x\n")
    (pkg / "application" / "b.py").write_text(
        "from resto.interface import y\nimport eval.z\nfrom resto.domain.m import _Hidden\n"
    )
    found = _violations(tmp_path)
    assert found["domain"] == ["resto/domain/a.py: pydantic", "resto/domain/a.py: resto.adapters"]
    assert found["application"] == ["resto/application/b.py: resto.interface"]
    assert found["eval"] == ["resto/application/b.py: eval.z"]
    assert found["private"] == ["resto/application/b.py: resto.domain.m._Hidden"]
