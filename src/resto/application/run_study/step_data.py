"""The task a `StepRecord` stores: a value dumped as JSON-ready data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from resto.application.schemas import adapter_for


def data(value: Any) -> Mapping[str, Any]:
    """`value` as the JSON-ready mapping stored in a `StepRecord`."""
    dumped: Mapping[str, Any] = adapter_for(type(value)).dump_python(value, mode="json")
    return dumped
