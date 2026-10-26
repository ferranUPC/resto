from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import AreaOfInterest, NetworkSource, PlaceName
from resto.domain.value_objects.topology_modification import TopologyModification


@dataclass(frozen=True, slots=True)
class NetworkRecipe:
    """Everything needed to rebuild a network without an LLM: OSM snapshot + netconvert
    options + plain-XML edits. Exactly one of `source` / `base_network_id`.

    An area of interest (box or polygon) requires the `osm_snapshot` it was imported from; a
    generated network and a derivation forbid it. A `PlaceName` is a request: the recipe stores
    the polygon it resolved to (ADR-0045)."""

    source: NetworkSource | None = None
    base_network_id: str | None = None
    osm_snapshot: ArtifactRef | None = None
    netconvert_options: tuple[str, ...] = ()
    plain_edits: tuple[TopologyModification, ...] = ()

    def __post_init__(self) -> None:
        if (self.source is None) == (self.base_network_id is None):
            raise ValueError("exactly one of source or base_network_id must be set")
        if isinstance(self.source, PlaceName):
            raise ValueError("a recipe stores the resolved Polygon, not the PlaceName")
        if self.source is not None and isinstance(self.source, AreaOfInterest):
            if self.osm_snapshot is None:
                raise ValueError("an area of interest requires an osm_snapshot artifact")
        elif self.osm_snapshot is not None:
            got = (
                "a derivation" if self.source is None else f"a source of kind {self.source.kind!r}"
            )
            raise ValueError(
                f"an osm_snapshot goes only with a bbox or polygon source, but this recipe has "
                f"{got}. Copy `source` and `osm_snapshot` exactly as the tool that built the "
                "network returned them"
            )

    @property
    def source_key(self) -> str | None:
        """Stable text for the source, the value the repositories filter `find(source=...)` by.
        None for a derivation."""
        return None if self.source is None else repr(self.source)

    @property
    def is_derivation(self) -> bool:
        return self.base_network_id is not None
