"""Alternate `tlLogic` programs for `signal_program` matrix rows: read a junction's own
`programID="0"` phases straight off `dev-net.net.xml` and retime them into a `programID="1"`
that `TlsProgramWriter`'s WAUT can switch to.

`_write_alt_program` in `verify/test_signal_program.py` hand-wrote this once for `C2` alone
(architecture doc E2.4); this generalises the same empirically-chosen retiming - durations
`(80, 3, 4, 3)` on top of the *unchanged* `state` strings, so the alternate program still respects
every junction's real connection layout - to any of DEV-NET's five corridor junctions, which all
share the same netconvert-default 4-phase (green, yellow, green, yellow) shape (verified by
inspection of `dev-net.net.xml` for A2/B2/C2/D2/E2), just with different `state` lengths (a 3-way
end junction like A2/E2 vs. a 4-way interior one like B2/C2/D2).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ALT_PROGRAM_ID = "1"
ORIGINAL_PROGRAM_ID = "0"
_ALT_DURATIONS = ("80", "3", "4", "3")


def read_phases(
    net_xml: Path, tls_id: str, program_id: str = ORIGINAL_PROGRAM_ID
) -> tuple[str, ...]:
    """The ordered `state` strings of `tls_id`'s `programID` on `net_xml`.

    Raises:
        ValueError: no `tlLogic` matches `(tls_id, program_id)`, or it is not the standard
            4-phase (green, yellow, green, yellow) shape this module knows how to retime.
    """
    root = ET.parse(net_xml).getroot()
    for tl in root.findall("tlLogic"):
        if tl.get("id") == tls_id and tl.get("programID") == program_id:
            phases = tuple(phase.get("state", "") for phase in tl.findall("phase"))
            if len(phases) != 4:
                raise ValueError(
                    f"tls {tls_id!r} program {program_id!r} has {len(phases)} phases, "
                    "expected the standard 4-phase shape"
                )
            return phases
    raise ValueError(f"no tlLogic {tls_id!r} program {program_id!r} in {net_xml}")


def write_alt_program(
    out_dir: Path, tls_id: str, net_xml: Path, alt_program_id: str = ALT_PROGRAM_ID
) -> Path:
    """Writes `<out_dir>/alt_program_<tls_id>.add.xml`: `tls_id`'s own phase `state` strings,
    retimed under `alt_program_id` - the file a `signal_program` row's WAUT switches to."""
    states = read_phases(net_xml, tls_id)
    root = ET.Element("additional")
    tl = ET.SubElement(
        root, "tlLogic", id=tls_id, type="static", programID=alt_program_id, offset="0"
    )
    for duration, state in zip(_ALT_DURATIONS, states, strict=True):
        ET.SubElement(tl, "phase", duration=duration, state=state)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"alt_program_{tls_id}.add.xml"
    ET.indent(root, space="    ")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return path
