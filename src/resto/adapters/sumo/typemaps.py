"""Where SUMO's own `netconvert` typemaps live, found from the installed `eclipse-sumo` package.

An absolute path, so a recipe's options do not depend on the working directory, and no `SUMO_HOME`
(ADR-0010)."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path


def typemap_dir() -> Path:
    spec = find_spec("sumo")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("the eclipse-sumo package is not installed")
    directory = Path(next(iter(spec.submodule_search_locations))) / "data" / "typemap"
    if not directory.is_dir():
        raise RuntimeError(f"the SUMO package has no typemap directory at {directory}")
    return directory.resolve()
