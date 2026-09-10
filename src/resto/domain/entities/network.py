from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.sanity_report import SanityReport


@dataclass(frozen=True, slots=True)
class Network:
    network_id: str
    net_xml_path: Path
    source: NetworkSource
    content_hash: str
    sanity_report: SanityReport | None = None

    def __post_init__(self) -> None:
        if self.net_xml_path.suffix != ".xml":
            raise ValueError("net_xml_path must point to a .net.xml file")
