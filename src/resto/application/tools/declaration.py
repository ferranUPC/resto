"""Declare a tool once: name, explicit description and a typed function (ADR-0033).

    @tool(name="get_edge", description="Attributes of one edge.")
    def get_edge(ctx: NetworkQuery, edge_id: Annotated[str, Field(description="Edge id.")]) -> ...

The input schema comes from the annotations of every parameter after the first. The first
parameter (`ctx`) carries what the model must not see or fill (a `NetworkQuery`, repositories); it
is left out of the schema and bound by `Declared.bind`. The schema is built when the decorator runs,
so a parameter that cannot be turned into a schema fails at import, not when a model calls the tool.

The description is written out, not read from the docstring: it changes what the model does, so it
is versioned with the agent and a docstring edit must not move it.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from functools import partial
from typing import Any, Concatenate, Generic, ParamSpec, TypeVar, get_type_hints

from pydantic import create_model

from resto.application.ports.llm import Tool

C = TypeVar("C")
P = ParamSpec("P")
R = TypeVar("R")


class Declared(Generic[C, P, R]):
    """A declared tool. Calling it is calling the typed function, `ctx` included."""

    def __init__(
        self,
        fn: Callable[Concatenate[C, P], R],
        name: str,
        description: str,
        input_schema: Mapping[str, Any],
        hints: Mapping[str, Any],
    ) -> None:
        self.fn = fn
        self.hints = hints
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def __call__(self, ctx: C, /, *args: P.args, **kwargs: P.kwargs) -> R:
        return self.fn(ctx, *args, **kwargs)

    def bind(self, ctx: C) -> Tool:
        """The `Tool` an agent or MCP server receives, with `ctx` fixed.

        `mcp.server.mcpserver` introspects `__name__`, `__doc__` and the signature of `fn`;
        `inspect.signature` drops the bound first argument of a `partial`, and the annotations are
        set already resolved because the MCP server cannot see this module's names.
        """
        bound = partial(self.fn, ctx)
        bound.__name__ = self.name  # type: ignore[attr-defined, union-attr]
        bound.__doc__ = self.fn.__doc__
        bound.__annotations__ = dict(self.hints)  # type: ignore[attr-defined]
        return Tool(
            name=self.name,
            description=self.description,
            fn=bound,
            input_schema=self.input_schema,
        )


def tool(
    *, name: str, description: str
) -> Callable[[Callable[Concatenate[C, P], R]], Declared[C, P, R]]:
    """Declare `fn` as a tool named `name`; `description` is what the model reads."""

    def declare(fn: Callable[Concatenate[C, P], R]) -> Declared[C, P, R]:
        hints = _hints(fn)
        return Declared(fn, name, description, derive_schema(fn, hints), hints)

    return declare


def _hints(fn: Callable[..., Any]) -> dict[str, Any]:
    hints = get_type_hints(fn, include_extras=True)
    first = next(iter(inspect.signature(fn).parameters), None)
    if first:
        hints.pop(first, None)
    return hints


def derive_schema(fn: Callable[..., Any], hints: Mapping[str, Any]) -> dict[str, Any]:
    """JSON schema of every parameter of `fn` after the first, in the shape the models get today.

    `hints` are the resolved annotations of `fn` without the first parameter (see `_hints`).

    Raises:
        TypeError: a parameter is not annotated, or `fn` has no `ctx` parameter.
        pydantic.errors.PydanticSchemaGenerationError: an annotation has no schema.
    """
    parameters = list(inspect.signature(fn).parameters.values())
    if not parameters:
        raise TypeError(f"{fn.__qualname__} needs a first `ctx` parameter")
    fields: dict[str, Any] = {}
    for parameter in parameters[1:]:
        if parameter.name not in hints:
            raise TypeError(f"{fn.__qualname__}: parameter `{parameter.name}` is not annotated")
        default = ... if parameter.default is inspect.Parameter.empty else parameter.default
        fields[parameter.name] = (hints[parameter.name], default)
    raw = create_model(fn.__name__, **fields).model_json_schema()
    return _normalize(raw)


def _normalize(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic's output without its extras, so it matches what the hand-written tables said.

    Drops `title` and `default` keys, and renders an optional parameter as its plain type instead
    of `anyOf` with `null`.
    """
    cleaned = _clean(schema)
    assert isinstance(cleaned, dict)
    cleaned.setdefault("properties", {})
    return cleaned


def _clean(node: Any) -> Any:
    if isinstance(node, list):
        return [_clean(item) for item in node]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node:
        options = [o for o in node["anyOf"] if o != {"type": "null"}]
        if len(options) == 1:
            rest = {k: v for k, v in node.items() if k != "anyOf"}
            return _clean({**options[0], **rest})
    return {
        key: _clean_value(key, value)
        for key, value in node.items()
        if key not in ("title", "default")
    }


def _clean_value(key: str, value: Any) -> Any:
    # under `properties` the keys are parameter names, so a parameter called `title` or `default`
    # must survive: clean each property schema, not the mapping itself
    if key == "properties" and isinstance(value, dict):
        return {name: _clean(sub) for name, sub in value.items()}
    return _clean(value)
