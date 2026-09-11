from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.topology_modification import TopologyModification


@dataclass(frozen=True, slots=True)
class NetworkRecipe:
    """Everything needed to rebuild a network without an LLM: OSM snapshot + netconvert
    options + plain-XML edits. Exactly one of `source` / `base_network_id`."""

    source: NetworkSource | None = None
    base_network_id: str | None = None
    osm_snapshot: ArtifactRef | None = None
    netconvert_options: tuple[str, ...] = ()
    plain_edits: tuple[TopologyModification, ...] = ()

    def __post_init__(self) -> None:
        if (self.source is None) == (self.base_network_id is None):
            raise ValueError("exactly one of source or base_network_id must be set")
        if (
            self.source is not None
            and self.source.needs_osm_snapshot
            and (self.osm_snapshot is None)
        ):
            raise ValueError("place/bbox sources require an osm_snapshot artifact")

    @property
    def is_derivation(self) -> bool:
        return self.base_network_id is not None
