"""`write_sumocfg` writer (ADR-0017): a `SimulationSettings` record becomes a `.sumocfg`.

Two callers, one renderer:

- the Scenario Builder writes the *scenario cfg* - inputs, time window, teleport policy; no seed,
  no outputs - which is the artifact a `Scenario` holds;
- the Runner reads that cfg back (`parse_settings`), rebases its paths to the run directory and
  renders the *run cfg* with `seed` and the fixed output block on top.

Every path in a rendered cfg is relative to the cfg's own directory, so the bytes (and the
`content_hash`) do not depend on where the artifact store lives. Rendered via `ElementTree`
(already the parser for `parse_settings` and `adapters/sumo/outputs.py`) rather than assembled by
hand: building the tree in a fixed section/option order and serializing it with `ET.indent` +
`ET.tostring` is exactly as byte-stable as hand-built strings - identical settings still mean an
identical file - without a bespoke indentation scheme to keep in sync by hand.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path, PurePosixPath

from resto.adapters.persistence.filesystem import artifact_ref
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef

_INPUT_OPTIONS = ("net-file", "route-files", "additional-files")
_KNOWN_OPTIONS: Mapping[str, tuple[str, ...]] = {
    "input": _INPUT_OPTIONS,
    "time": ("begin", "end", "step-length"),
    "processing": ("time-to-teleport",),
}


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _relative(path: Path, cfg_dir: Path) -> str:
    rel = os.path.relpath(path.resolve(), cfg_dir.resolve())
    return PurePosixPath(Path(rel)).as_posix()


def _file_list(paths: tuple[Path, ...], cfg_dir: Path) -> str:
    return ",".join(_relative(p, cfg_dir) for p in paths)


def _render(root: ET.Element) -> str:
    """`root`, indented, as text - no XML declaration (SUMO does not require one, and neither
    the current scenario nor run cfgs carry one)."""
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode") + "\n"


def render_sumocfg(
    settings: SimulationSettings,
    cfg_dir: Path,
    *,
    seed: int | None = None,
    outputs: Mapping[str, str] | None = None,
    report: Mapping[str, str] | None = None,
) -> str:
    """The cfg text for `settings`, with paths relative to `cfg_dir`. `seed`, `outputs`
    (`output` option -> file name) and `report` are what turns a scenario cfg into a run cfg."""
    root = ET.Element("configuration")

    input_el = ET.SubElement(root, "input")
    ET.SubElement(input_el, "net-file", value=_relative(settings.net_file, cfg_dir))
    ET.SubElement(input_el, "route-files", value=_file_list(settings.route_files, cfg_dir))
    if settings.additional_files:
        additional = _file_list(settings.additional_files, cfg_dir)
        ET.SubElement(input_el, "additional-files", value=additional)

    time_el = ET.SubElement(root, "time")
    ET.SubElement(time_el, "begin", value=_num(settings.begin))
    if settings.end is not None:
        ET.SubElement(time_el, "end", value=_num(settings.end))
    ET.SubElement(time_el, "step-length", value=_num(settings.step_length))

    processing_el = ET.SubElement(root, "processing")
    ET.SubElement(processing_el, "time-to-teleport", value=_num(settings.time_to_teleport))

    if seed is not None:
        random_el = ET.SubElement(root, "random_number")
        ET.SubElement(random_el, "seed", value=str(seed))

    if outputs:
        output_el = ET.SubElement(root, "output")
        for option, name in outputs.items():
            ET.SubElement(output_el, option, value=name)

    if report:
        report_el = ET.SubElement(root, "report")
        for option, value in report.items():
            ET.SubElement(report_el, option, value=value)

    return _render(root)


def parse_settings(cfg_path: Path) -> SimulationSettings:
    """Reads a scenario cfg back into `SimulationSettings` with absolute paths.

    Raises:
        ValueError: the cfg carries a section or option this writer does not produce (a seed, an
            output, ...): the Runner would silently drop it when deriving the run cfg.
    """
    root = ET.parse(cfg_path).getroot()
    cfg_dir = cfg_path.resolve().parent
    values: dict[str, str] = {}
    for section in root:
        known = _KNOWN_OPTIONS.get(section.tag)
        if known is None:
            raise ValueError(
                f"{cfg_path.name}: unexpected section <{section.tag}> in a scenario cfg"
            )
        for option in section:
            if option.tag not in known:
                raise ValueError(
                    f"{cfg_path.name}: unexpected option <{option.tag}> in a scenario cfg"
                )
            values[option.tag] = option.get("value", "")
    if "net-file" not in values or "route-files" not in values:
        raise ValueError(f"{cfg_path.name}: a scenario cfg needs net-file and route-files")

    def files(option: str) -> tuple[Path, ...]:
        raw = values.get(option, "")
        return tuple((cfg_dir / p).resolve() for p in raw.split(",") if p)

    return SimulationSettings(
        net_file=files("net-file")[0],
        route_files=files("route-files"),
        additional_files=files("additional-files"),
        begin=float(values.get("begin", 0.0)),
        end=float(values["end"]) if "end" in values else None,
        step_length=float(values.get("step-length", 1.0)),
        time_to_teleport=float(values.get("time-to-teleport", 300.0)),
    )


class SumocfgFileWriter:
    """`SumocfgWriter` port: writes `<out_dir>/<name>` and returns its `ArtifactRef`."""

    def write(self, settings: SimulationSettings, out_dir: Path, name: str) -> ArtifactRef:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / name
        path.write_text(render_sumocfg(settings, out_dir), encoding="utf-8")
        return artifact_ref(path, "sumocfg")


def write_edgedata_additional(out_dir: Path, period_s: float, output_name: str) -> Path:
    """The `<edgeData>` additional that makes SUMO write interval-aggregated edgedata to
    `<out_dir>/<output_name>` (SUMO resolves the `file` attribute relative to the additional
    file itself). `--edgedata-output` has no period option in 1.27.1, hence this file."""
    root = ET.Element("additional")
    ET.SubElement(root, "edgeData", id="resto_edgedata", freq=_num(period_s), file=output_name)
    path = out_dir / "edgedata.add.xml"
    path.write_text(_render(root), encoding="utf-8")
    return path


def with_additional(settings: SimulationSettings, *extra: Path) -> SimulationSettings:
    return replace(settings, additional_files=settings.additional_files + tuple(extra))
