"""Golden path definitions: request, prior world state and expected trace.

One module per golden path. `discover` returns every `GoldenPath` the modules define, so adding a
path edits no central list.
"""

from __future__ import annotations

import importlib
import pkgutil

from golden.framework.expected import GoldenPath


def discover() -> tuple[GoldenPath, ...]:
    """Every `GoldenPath` defined at module level in this package, sorted by name."""
    found: dict[str, GoldenPath] = {}
    for module in pkgutil.iter_modules(__path__):
        loaded = importlib.import_module(f"{__name__}.{module.name}")
        for value in vars(loaded).values():
            if isinstance(value, GoldenPath):
                found[value.name] = value
    return tuple(found[name] for name in sorted(found))
