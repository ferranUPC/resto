"""`AdditionalFileWriter` for the `speed_limit` mechanism (DoD §2.5, ADR-0007): a
`variableSpeedSign` with a two-step time profile — set the limit at the window's start, revert
at its end.

Pure deterministic code, no LLM involved. `variableSpeedSign` operates on lane ids, not edge ids,
and this writer has no network access to expand an edge into its lanes — it only supports a
`LaneTarget` (one lane). An edge-wide speed_limit needs one intervention per lane, decided by
whoever assembles the interventions (agent or Coordinator), or is a case for `rejected[]`
(ADR-0007: no silent coercion).

`params` contract (free-form on `Intervention`, fixed here by this writer):
  - `speed` (required): target speed in m/s during the window.
  - `revert_speed` (required): speed in m/s to restore once the window ends — this writer does
    not look the original speed up itself, so the caller (the agent, via `get_lanes`/`get_edge`)
    must supply it.
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


class VssWriter:
    """`AdditionalFileWriter` port: `speed_limit` interventions with a fixed `window` on a
    single lane."""

    def supports(self, intervention: Intervention) -> bool:
        return (
            intervention.type is InterventionType.SPEED_LIMIT
            and intervention.strategy is Strategy.STATIC
            and isinstance(intervention.target, LaneTarget)
        )

    def write(
        self, intervention: Intervention, out_dir: Path
    ) -> tuple[StaticFileMechanism, ArtifactRef]:
        """Writes `<out_dir>/vss_<lane_id>.add.xml`.

        Raises:
            ValueError: `intervention` is not a static `speed_limit` on a `LaneTarget`, or
                `params` is missing `speed`/`revert_speed` — check `supports` first.
        """
        if not self.supports(intervention):
            raise ValueError("VssWriter only handles a static speed_limit on a LaneTarget")
        if "speed" not in intervention.params:
            raise ValueError("a speed_limit intervention needs params['speed']")
        if "revert_speed" not in intervention.params:
            raise ValueError("a speed_limit intervention needs params['revert_speed']")
        target = intervention.target
        assert isinstance(target, LaneTarget)  # narrowed by supports()
        window = intervention.window
        assert window is not None  # static strategy guarantees this
        speed = float(intervention.params["speed"])
        revert_speed = float(intervention.params["revert_speed"])

        root = ET.Element("additional")
        vss = ET.SubElement(
            root, "variableSpeedSign", id=f"vss_{target.lane_id}", lanes=target.lane_id
        )
        ET.SubElement(vss, "step", time=_num(window.start), speed=_num(speed))
        ET.SubElement(vss, "step", time=_num(window.end), speed=_num(revert_speed))

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"vss_{target.lane_id}.add.xml"
        path.write_text(_render(root), encoding="utf-8")
        ref = artifact_ref(path, "additional")
        return StaticFileMechanism(file_kind="vss", path=ref.path), ref
