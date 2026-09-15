"""`AdditionalFileWriter` for the `lane_closure` mechanism (DoD §2.5, ADR-0007): a rerouter with
`closingLaneReroute`, placed on the same edge as the closed lane.

Pure deterministic code, no LLM involved (ADR-0007) — the Builder agent calls this as the
`write_rerouter` tool once it has decided `lane_closure` is the right intervention and the window
is fixed. Static (`window`) only; a runtime `condition` needs a script, not this writer.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism


def _render(root: ET.Element) -> str:
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode") + "\n"


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


class RerouterWriter:
    """`AdditionalFileWriter` port: `lane_closure` interventions with a fixed `window`."""

    def supports(self, intervention: Intervention) -> bool:
        return (
            intervention.type is InterventionType.LANE_CLOSURE
            and intervention.strategy is Strategy.STATIC
            and isinstance(intervention.target, LaneTarget)
        )

    def write(
        self, intervention: Intervention, out_dir: Path
    ) -> tuple[StaticFileMechanism, ArtifactRef]:
        """Writes `<out_dir>/rerouter_<lane_id>.add.xml`.

        Raises:
            ValueError: `intervention` is not a static `lane_closure` on a `LaneTarget` — check
                `supports` first.
        """
        if not self.supports(intervention):
            raise ValueError("RerouterWriter only handles a static lane_closure on a LaneTarget")
        target = intervention.target
        assert isinstance(target, LaneTarget)  # narrowed by supports()
        window = intervention.window
        assert window is not None  # static strategy guarantees this

        root = ET.Element("additional")
        rerouter = ET.SubElement(
            root, "rerouter", id=f"rerouter_{target.lane_id}", edges=target.edge_id
        )
        interval = ET.SubElement(
            rerouter, "interval", begin=_num(window.start), end=_num(window.end)
        )
        ET.SubElement(interval, "closingLaneReroute", id=target.lane_id)

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"rerouter_{target.lane_id}.add.xml"
        path.write_text(_render(root), encoding="utf-8")
        ref = artifact_ref(path, "additional")
        return StaticFileMechanism(file_kind="rerouter", path=ref.path), ref
