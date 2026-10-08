"""One module per golden path, each defining `SCRIPT: AgentScript`. See `golden.setups.fake`."""

from __future__ import annotations

import importlib
import pkgutil

from golden.setups.fake.script import AgentScript


def discover() -> dict[str, AgentScript]:
    """The scripts of this package keyed by module name, which is the golden path's name."""
    found: dict[str, AgentScript] = {}
    for module in pkgutil.iter_modules(__path__):
        loaded = importlib.import_module(f"{__name__}.{module.name}")
        script = getattr(loaded, "SCRIPT", None)
        if not isinstance(script, AgentScript):
            raise TypeError(f"{loaded.__name__} must define SCRIPT = AgentScript(...)")
        found[module.name] = script
    return found
