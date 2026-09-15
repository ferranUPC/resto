"""`AdditionalFileWriter` for the `lane_closure` and `edge_closure` mechanisms (DoD §2.5,
ADR-0007): a rerouter with `closingLaneReroute` (one lane) or `closingReroute` (a whole edge).

Pure deterministic code, no LLM involved (ADR-0007) — the Builder agent calls this as the
`write_rerouter` tool once it has decided `lane_closure`/`edge_closure` is the right intervention
and the window is fixed. Static (`window`) only; a runtime `condition` needs a script, not this
writer.

`closingReroute` needs an explicit `disallow="all"` - found empirically while building E2.4's
effect-verification harness: without it, `additional_file.xsd`'s `closingReroute` element (unlike
`closingLaneReroute`, which is unambiguous - there is nothing else a single lane could mean)
leaves every vehicle class allowed by default, so the edge stays open in practice and the flow
check E2.4 grades this against never goes to zero.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism


def _render(root: ET.Element) -> str:
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode") + "\n"


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


class RerouterWriter:
    """`AdditionalFileWriter` port: `lane_closure` (on a `LaneTarget`) and `edge_closure` (on an
    `EdgeTarget`) interventions with a fixed `window`."""

    def supports(self, intervention: Intervention) -> bool:
        if intervention.strategy is not Strategy.STATIC:
            return False
        if intervention.type is InterventionType.LANE_CLOSURE:
            return isinstance(intervention.target, LaneTarget)
        if intervention.type is InterventionType.EDGE_CLOSURE:
            return isinstance(intervention.target, EdgeTarget)
        return False

    def write(
        self, intervention: Intervention, out_dir: Path
    ) -> tuple[StaticFileMechanism, ArtifactRef]:
        """Writes `<out_dir>/rerouter_<lane_id|edge_id>.add.xml`.

        Raises:
            ValueError: `intervention` is not a static `lane_closure` on a `LaneTarget` or a
                static `edge_closure` on an `EdgeTarget` — check `supports` first.
        """
        if not self.supports(intervention):
            raise ValueError(
                "RerouterWriter only handles a static lane_closure on a LaneTarget or a static "
                "edge_closure on an EdgeTarget"
            )
        target = intervention.target
        window = intervention.window
        assert window is not None  # static strategy guarantees this

        if isinstance(target, LaneTarget):
            closed_id, reroute_tag = target.lane_id, "closingLaneReroute"
        else:
            assert isinstance(target, EdgeTarget)  # narrowed by supports()
            closed_id, reroute_tag = target.edge_id, "closingReroute"

        root = ET.Element("additional")
        rerouter = ET.SubElement(
            root, "rerouter", id=f"rerouter_{closed_id}", edges=target.edge_id
        )
        interval = ET.SubElement(
            rerouter, "interval", begin=_num(window.start), end=_num(window.end)
        )
        reroute_attrib = {"id": closed_id}
        if reroute_tag == "closingReroute":
            reroute_attrib["disallow"] = "all"
        ET.SubElement(interval, reroute_tag, reroute_attrib)

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"rerouter_{closed_id}.add.xml"
        path.write_text(_render(root), encoding="utf-8")
        ref = artifact_ref(path, "additional")
        return StaticFileMechanism(file_kind="rerouter", path=ref.path), ref
