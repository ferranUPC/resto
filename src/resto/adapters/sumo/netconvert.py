"""`NetconvertRunner` adapter: `netgenerate` for generated networks, `netconvert` for OSM or plain
XML, and the plain-XML export (ADR-0003, ADR-0045).

Every network is written as `network.net.xml` in the directory the caller gives, and its
`ArtifactRef` hashes the canonical bytes, so SUMO's generated-on header never reaches the hash.
Both tools run through `launch`, which pins the SUMO version.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from resto.adapters.sumo.outputs import output_artifact
from resto.adapters.sumo.sumo_process import launch
from resto.application.ports.sumo import NetBuildError
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import (
    GeneratedNetwork,
    GridNetwork,
    RandomNetwork,
    SpiderNetwork,
)

NET_NAME = "network.net.xml"
PLAIN_PREFIX = "plain"
_PLAIN_FILES = (
    ("--node-files", ".nod.xml"),
    ("--edge-files", ".edg.xml"),
    ("--connection-files", ".con.xml"),
    ("--tllogic-files", ".tll.xml"),
    ("--type-files", ".typ.xml"),
)


class SubprocessNetconvertRunner:
    """`NetconvertRunner` over the `netgenerate` and `netconvert` binaries on PATH."""

    def generate(self, source: GeneratedNetwork, out_dir: Path) -> ArtifactRef:
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / NET_NAME
        seed = source.seed if isinstance(source, RandomNetwork) else 0
        result = launch(
            "netgenerate", [*_generate_args(source), "--output-file", str(out)], out_dir, seed
        )
        if not result.ok:
            raise NetBuildError(f"netgenerate failed: {result.message}")
        return output_artifact(out, "net")

    def build(
        self, osm: ArtifactRef | None, plain_dir: Path | None, options: Sequence[str], out_dir: Path
    ) -> ArtifactRef:
        if (osm is None) == (plain_dir is None):
            raise ValueError("build takes exactly one of an OSM snapshot or a plain XML directory")
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / NET_NAME
        inputs = ["--osm-files", str(osm.path)] if osm else _plain_inputs(plain_dir)
        result = launch(
            "netconvert", [*inputs, *options, "--output-file", str(out)], out_dir, seed=0
        )
        if not result.ok:
            raise NetBuildError(f"netconvert failed: {result.message}")
        return output_artifact(out, "net")

    def export_plain(self, net_xml: ArtifactRef, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        result = launch(
            "netconvert",
            [
                "--sumo-net-file",
                str(net_xml.path),
                "--plain-output-prefix",
                str(out_dir / PLAIN_PREFIX),
            ],
            out_dir,
            seed=0,
        )
        if not result.ok:
            raise NetBuildError(f"netconvert failed: {result.message}")
        return out_dir


def _plain_inputs(plain_dir: Path | None) -> list[str]:
    assert plain_dir is not None
    args: list[str] = []
    for option, suffix in _PLAIN_FILES:
        found = sorted(plain_dir.glob(f"*{suffix}"))
        if found:
            args += [option, ",".join(str(p) for p in found)]
    return args


def _generate_args(source: GeneratedNetwork) -> list[str]:
    match source:
        case GridNetwork():
            return [
                "--grid",
                "--grid.x-number",
                str(source.x_number),
                "--grid.y-number",
                str(source.y_number),
                "--grid.x-length",
                str(source.x_length),
                "--grid.y-length",
                str(source.y_length),
            ]
        case SpiderNetwork():
            return [
                "--spider",
                "--spider.arm-number",
                str(source.arm_number),
                "--spider.circle-number",
                str(source.circle_number),
                "--spider.space-radius",
                str(source.space_radius),
                *(["--spider.omit-center"] if source.omit_center else []),
            ]
        case RandomNetwork():
            return [
                "--rand",
                "--rand.iterations",
                str(source.iterations),
                "--rand.min-distance",
                str(source.min_distance),
                "--rand.max-distance",
                str(source.max_distance),
            ]
