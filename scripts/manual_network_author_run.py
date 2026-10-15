"""Manual run of the Network Author with the default model (E6.1 ticket 08).

Not a pytest test (docs/llm-cost-policy.md). The model, `netconvert`, `netgenerate`, the sanity
check and the promoter are real. OpenStreetMap is not reachable: the geocoder and Overpass fail by
name, so the request must be answerable with a generated network (or `Found`, `NeedsUser`).

    python scripts/manual_network_author_run.py "a 5 by 5 grid" --work DIR            # dry run
    python scripts/manual_network_author_run.py "a 5 by 5 grid" --work DIR --run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from resto.adapters.llm.agents.network_author import NetworkAuthorCollaborators, NetworkAuthorPort
from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
from resto.adapters.llm.config import load_llm_config
from resto.adapters.llm.pricing import estimate_cost_usd
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.network_probe import SumoNetworkProber
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.ports.llm import Budget
from resto.application.ports.osm import ExternalServiceError, OsmLimits
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

    def fetch(self, area: BBox | Polygon, out_dir: Path) -> ArtifactRef:
        raise ExternalServiceError("overpass", "offline in this manual run")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("network_ref")
    ap.add_argument("--run", action="store_true")
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
    port = NetworkAuthorPort(
        agent=OpenRouterToolAgent(config),
        budget=budget,
        collaborators=NetworkAuthorCollaborators(
            networks=db.networks,
            runner=runner,
            editor=editor,
            prober=SumoNetworkProber(SubprocessSumoRunner()),
            open_network=SumolibNetworkQuery,
            osm=offline,
            geocoder=offline,
            typemap_dir=typemap_dir(),
            out_dir=args.work / "author",
            limits=OsmLimits(),
        ),
    )
    task = ObtainNetworkTask(args.network_ref, max_rounds=MAX_ROUNDS)
    try:
        run = port.obtain(task)
        print(f"stop: {run.stop_reason}  usage: {run.usage}")
        for call in run.tool_calls:
            print(f"  tool {call.name}")
        print(f"outcome: {run.output}")
        if run.output is not None and hasattr(run.output, "net_artifact"):
            network = NetworkPromoter(runner, editor).promote(run, task)  # type: ignore[arg-type]
            print(f"promoted: {network.network_id}  hash {network.net_xml.content_hash}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
