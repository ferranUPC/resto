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
    `recipe` rebuilds it without an LLM."""

    network_id: str
    net_xml: ArtifactRef
    recipe: NetworkRecipe
    sanity_report: SanityReport
    sumo_version: str = SUMO_VERSION
    derived_from: str | None = None
    probe_report: ProbeReport | None = None

    def __post_init__(self) -> None:
        if not self.net_xml.path.name.endswith(".net.xml"):
            raise ValueError("net_xml must point to a .net.xml file")
        if self.network_id != self.net_xml.content_hash:
            raise ValueError("network_id must equal the content hash of the .net.xml")
        if self.recipe.base_network_id != self.derived_from:
            raise ValueError("derived_from must equal recipe.base_network_id")
        if self.sumo_version != SUMO_VERSION:
            raise ValueError(f"networks must be built with SUMO {SUMO_VERSION}")

    @property
    def content_hash(self) -> str:
        return self.net_xml.content_hash
