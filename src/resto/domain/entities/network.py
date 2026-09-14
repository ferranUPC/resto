from __future__ import annotations

from dataclasses import dataclass

from resto.domain.constants import SUMO_VERSION
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.probe_report import ProbeReport
from resto.domain.value_objects.sanity_report import SanityReport


@dataclass(frozen=True, slots=True)
class Network:
    """A compiled SUMO network. `network_id` is the content hash of the .net.xml;
    `recipe` rebuilds it without an LLM.

    `label` is a human-facing, opaque handle (DATABASE_MCP_CONTRACT.md §10, open point 1) — e.g.
    `"berlin/remove_edge_118"` for a network derived from a "berlin" one. It carries no identity
    claim: it is not part of `network_id`, and unlike `net_xml`/`recipe`/`sanity_report` a repeat
    `store_network` may update it on an existing id without that being a CONFLICT (contract §3).
    Hierarchy implied by a `/` in the string is a naming convention only — domain does not parse
    or enforce it, the same way an object store treats a key as an opaque path."""

    network_id: str
    net_xml: ArtifactRef
    recipe: NetworkRecipe
    sanity_report: SanityReport
    sumo_version: str = SUMO_VERSION
    derived_from: str | None = None
    probe_report: ProbeReport | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.net_xml.path.name.endswith(".net.xml"):
            raise ValueError("net_xml must point to a .net.xml file")
        if self.network_id != self.net_xml.content_hash:
            raise ValueError("network_id must equal the content hash of the .net.xml")
        if self.recipe.base_network_id != self.derived_from:
            raise ValueError("derived_from must equal recipe.base_network_id")
        if self.sumo_version != SUMO_VERSION:
            raise ValueError(f"networks must be built with SUMO {SUMO_VERSION}")
        if self.label is not None and not self.label.strip():
            raise ValueError("label must not be blank when given")

    @property
    def content_hash(self) -> str:
        return self.net_xml.content_hash
