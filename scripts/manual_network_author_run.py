"""Manual run of the Network Author with the default model (E6.1 ticket 08).

Not a pytest test (docs/llm-cost-policy.md). The model, `netconvert`, `netgenerate`, the sanity
check and the promoter are real. By default OpenStreetMap is not reachable: the geocoder and
Overpass fail by name, so the request must be answerable with a generated network (or `Found`,
`NeedsUser`).

    python scripts/manual_network_author_run.py "a 5 by 5 grid" --work DIR            # dry run
    python scripts/manual_network_author_run.py "a 5 by 5 grid" --work DIR --run
    python scripts/manual_network_author_run.py "Adlershof, Berlin" --work DIR --run --online --gui

`--online` uses the real Nominatim and Overpass; `--gui` opens the resulting network in `sumo-gui`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from resto.adapters.llm.agents.network_author import NetworkAuthorCollaborators, NetworkAuthorPort
from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
from resto.adapters.llm.config import load_llm_config
from resto.adapters.llm.pricing import estimate_cost_usd
from resto.adapters.osm.nominatim import NominatimGeocoder
from resto.adapters.osm.overpass import OverpassOsmSource
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.network_probe import SumoNetworkProber
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.outputs import output_artifact
from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.ports.llm import Budget
from resto.application.ports.osm import (
    ExternalServiceError,
    Geocoder,
    LocatedPlace,
    OsmLimits,
    OsmSource,
)
from resto.application.promoters.network import NetworkPromoter
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, PlaceName, Polygon
from resto.domain.value_objects.tasks import ObtainNetworkTask
from resto.interface.dependencies import NETWORK_AUTHOR_SECONDS, NETWORK_AUTHOR_STEPS

MAX_ROUNDS = 3
# Each step re-sends the conversation so far; a generous bound for the worst case.
INPUT_TOKENS_PER_STEP = 10_000


class _Offline:
    """Stands for Nominatim and Overpass: this run must not reach a public service."""

    def resolve(self, place: PlaceName) -> Polygon:
        raise ExternalServiceError("nominatim", "offline in this manual run")

    def locate(self, query: str) -> LocatedPlace | None:
        raise ExternalServiceError("nominatim", "offline in this manual run")

    def fetch(self, area: BBox | Polygon, out_dir: Path) -> ArtifactRef:
        raise ExternalServiceError("overpass", "offline in this manual run")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("network_ref")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--online", action="store_true", help="real Nominatim and Overpass")
    ap.add_argument("--gui", action="store_true", help="open the network in sumo-gui")
    ap.add_argument("--work", type=Path, required=True, help="empty directory for db and files")
    args = ap.parse_args()

    config = load_llm_config()
    budget = Budget(NETWORK_AUTHOR_STEPS, config.max_output_tokens, NETWORK_AUTHOR_SECONDS)
    worst = estimate_cost_usd(
        config.default_model,
        NETWORK_AUTHOR_STEPS * INPUT_TOKENS_PER_STEP,
        NETWORK_AUTHOR_STEPS * config.max_output_tokens,
    )
    print(f"model {config.default_model}  budget {budget}  rounds {MAX_ROUNDS}")
    print(f"worst-case cost: ${worst:.3f} ({NETWORK_AUTHOR_STEPS} steps)")
    if not args.run:
        print("dry run: no API call made")
        return 0

    args.work.mkdir(parents=True, exist_ok=True)
    db = SqliteDatabase(args.work / "resto.sqlite")
    runner = SubprocessNetconvertRunner()
    editor = XmlPlainNetEditor()
    offline = _Offline()
    osm: OsmSource = OverpassOsmSource() if args.online else offline
    geocoder: Geocoder = NominatimGeocoder(args.work / "geocoder") if args.online else offline
    port = NetworkAuthorPort(
        agent=OpenRouterToolAgent(config),
        budget=budget,
        collaborators=NetworkAuthorCollaborators(
            networks=db.networks,
            runner=runner,
            editor=editor,
            prober=SumoNetworkProber(SubprocessSumoRunner()),
            open_network=SumolibNetworkQuery,
            osm=osm,
            geocoder=geocoder,
            typemap_dir=typemap_dir(),
            out_dir=args.work / "author",
            limits=OsmLimits(),
        ),
    )
    task = ObtainNetworkTask(args.network_ref, max_rounds=MAX_ROUNDS)
    try:
        run = port.obtain(task)
        print(f"stop: {run.stop_reason}  usage: {run.usage}")
        for number, step in enumerate(run.steps, 1):
            calls = ",".join(step.tool_calls) or "(text only)"
            print(
                f"  step {number:2d}  {step.finish_reason}  in {step.input_tokens}  "
                f"out {step.output_tokens}  {calls}"
            )
        for call in run.tool_calls:
            print(f"  tool {call.name}")
            if call.result_summary.startswith(("validation failed", "invalid", "error")):
                print(f"    {call.result_summary[:600]}")
        transcript = args.work / "transcript.json"
        transcript.write_text(
            json.dumps(
                {
                    "request": args.network_ref,
                    "steps": [asdict(step) for step in run.steps],
                    "tool_calls": [asdict(call) for call in run.tool_calls],
                },
                indent=2,
                default=str,
                ensure_ascii=False,
            )
        )
        print(f"transcript: {transcript}")
        print(f"outcome: {run.output}")
        if run.output is not None and hasattr(run.output, "net_artifact"):
            claimed = run.output.net_artifact
            on_disk = output_artifact(claimed.path, "net").content_hash
            print(f"hash declared by the draft: {claimed.content_hash}")
            print(
                f"hash of the file on disk:   {on_disk}  "
                f"({'same' if on_disk == claimed.content_hash else 'DIFFERENT'})"
            )
            network = NetworkPromoter(runner, editor).promote(run, task)  # type: ignore[arg-type]
            print(f"promoted: {network.network_id}  hash {network.net_xml.content_hash}")
            if args.gui:
                subprocess.run(["sumo-gui", "-n", str(run.output.net_artifact.path)], check=False)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
