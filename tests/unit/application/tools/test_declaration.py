"""Tool declaration (ADR-0033): the schema is derived from the signature, `ctx` stays out of it,
and a parameter that cannot become a schema fails when the tool is declared."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

import pytest
from pydantic import Field
from pydantic.errors import PydanticSchemaGenerationError

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.tools.declaration import tool
from resto.application.tools.network import build_network_tools
from tests.unit._paths import DEV_NET


class Secret:
    """Stands for a collaborator the model must not see."""


@tool(name="probe", description="A probe.")
def probe(
    ctx: Secret,
    name: Annotated[str, Field(description="A name.")],
    window: Sequence[float] | None = None,
    top_k: int = 10,
) -> str:
    return name


def test_ctx_is_left_out_of_the_derived_schema() -> None:
    assert "ctx" not in probe.input_schema["properties"]
    assert set(probe.input_schema["properties"]) == {"name", "window", "top_k"}


def test_schema_is_normalized_to_plain_types_without_titles_or_defaults() -> None:
    assert probe.input_schema == {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "A name."},
            "window": {"type": "array", "items": {"type": "number"}},
            "top_k": {"type": "integer"},
        },
        "required": ["name"],
    }


def test_a_declared_tool_is_still_callable_with_its_context() -> None:
    assert probe(Secret(), "x") == "x"


def test_bound_tool_takes_only_the_model_facing_arguments() -> None:
    bound = probe.bind(Secret())

    assert (bound.name, bound.description) == ("probe", "A probe.")
    assert bound.fn(name="x") == "x"


def test_a_parameter_without_a_schema_fails_at_declaration() -> None:
    with pytest.raises(PydanticSchemaGenerationError):

        @tool(name="bad", description="Bad.")
        def bad(ctx: Secret, thing: Secret) -> None: ...


def test_an_unannotated_parameter_fails_at_declaration() -> None:
    with pytest.raises(TypeError, match="not annotated"):

        @tool(name="bad", description="Bad.")
        def bad(ctx: Secret, thing) -> None:  # type: ignore[no-untyped-def]  # noqa: ANN001
            ...


def test_no_network_tool_schema_mentions_ctx() -> None:
    tools = build_network_tools(SumolibNetworkQuery(DEV_NET))

    assert all("ctx" not in t.input_schema["properties"] for t in tools)
