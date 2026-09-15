"""`AdditionalFileWriter` for the `signal_program` mechanism (DoD §2.5, ADR-0007): a `WAUT`
(SUMO's program-switching construct, `additional_file.xsd`'s `WAUTType`/`wautJunctionType`) that
switches a junction's active `tlLogic` program to an alternate one for the window, then switches
it back.

Pure deterministic code, no LLM involved. The alternate program (`params["program_id"]`) must
already exist on the network as a second `tlLogic` for that junction — this writer only wires the
switch, it does not author TLS programs (that is Network Author territory). `params` contract:
  - `program_id` (required): the `tlLogic` `programID` to switch to for the window.
  - `original_program_id` (optional, default `"0"`, SUMO's default `programID`): the program to
    resume once the window ends.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy
from resto.domain.value_objects.intervention_target import TlsTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism

DEFAULT_PROGRAM_ID = "0"


def _render(root: ET.Element) -> str:
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode") + "\n"


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


class TlsProgramWriter:
    """`AdditionalFileWriter` port: `signal_program` interventions with a fixed `window` on a
    `TlsTarget`, implemented as a WAUT switch."""

    def supports(self, intervention: Intervention) -> bool:
        return (
            intervention.type is InterventionType.SIGNAL_PROGRAM
            and intervention.strategy is Strategy.STATIC
            and isinstance(intervention.target, TlsTarget)
        )

    def write(
        self, intervention: Intervention, out_dir: Path
    ) -> tuple[StaticFileMechanism, ArtifactRef]:
        """Writes `<out_dir>/waut_<tls_id>.add.xml`.

        Raises:
            ValueError: `intervention` is not a static `signal_program` on a `TlsTarget`, or
                `params` is missing `program_id` — check `supports` first.
        """
        if not self.supports(intervention):
            raise ValueError("TlsProgramWriter only handles a static signal_program on a TlsTarget")
        if "program_id" not in intervention.params:
            raise ValueError("a signal_program intervention needs params['program_id']")
        target = intervention.target
        assert isinstance(target, TlsTarget)  # narrowed by supports()
        window = intervention.window
        assert window is not None  # static strategy guarantees this
        program_id = str(intervention.params["program_id"])
        original_program_id = str(
            intervention.params.get("original_program_id", DEFAULT_PROGRAM_ID)
        )

        waut_id = f"waut_{target.tls_id}"
        root = ET.Element("additional")
        waut = ET.SubElement(
            root, "WAUT", id=waut_id, startProg=original_program_id, refTime="0"
        )
        ET.SubElement(waut, "wautSwitch", time=_num(window.start), to=program_id)
        ET.SubElement(waut, "wautSwitch", time=_num(window.end), to=original_program_id)
        ET.SubElement(
            root,
            "wautJunction",
            wautID=waut_id,
            junctionID=target.tls_id,
            procedure="Explicit",
            synchron="false",
        )

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{waut_id}.add.xml"
        path.write_text(_render(root), encoding="utf-8")
        ref = artifact_ref(path, "additional")
        return StaticFileMechanism(file_kind="tls_program", path=ref.path), ref
