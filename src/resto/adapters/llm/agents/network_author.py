"""Configuration of the Network Author: system prompt, tool list, output type, budget (DoD §2.2;
ADR-0001, ADR-0033, ADR-0037 §3, ADR-0045).

Wiring, not decisions about networks: the loop lives in the `ToolAgent` implementation, tool
behaviour in `application/tools/network_*`, and the checks on what the agent returns (recipe replay,
sanity, `unresolved[]`) in `application/promoters/network.py`. This module assembles the
`AgentTask`, the tools and the `Budget` for one `ObtainNetworkTask` or `NetworkTask` and calls the
agent. Besides that it does two small things of its own: `author` loads the base network and puts a
copy of its `.net.xml` in the working directory (the inspection tools read only there), and it
raises a service failure again after the run (below).

Two things the tools alone cannot do are done here:

- A fresh working state per call: `ImportRun` keeps the snapshots one agent run fetched, so each
  `obtain` or `author` builds its own and two runs never see each other's.
- A failing public service ends the step by name. The real `ToolAgent` hands a tool's exception back
  to the model as feedback; an `ExternalServiceError` is not the model's to fix, so the tool still
  raises it for the model, remembers it, and the port raises it again once the run is over.

A round is one repair cycle (edit, recompile, `sanity_check`), counted here as one `sanity_check`
call. The task's `max_rounds` is told to the model and also imposed in code: once that many rounds
are spent, every further tool call is refused, and a draft that still fails the sanity check with
nothing reported gets the failure added to its `unresolved[]`. The number of tool calls is limited
separately, by the `Budget`.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from resto.application.ports.llm import AgentRun, AgentTask, Budget, Tool, ToolAgent
from resto.application.ports.network_probe import NetworkProber
from resto.application.ports.network_query import EnumerableNetworkQuery, NetworkNotStored
from resto.application.ports.osm import ExternalServiceError, Geocoder, OsmLimits, OsmSource
from resto.application.ports.repositories import NetworkRepository
from resto.application.ports.sumo import NetconvertRunner, PlainNetEditor
from resto.application.tools.declaration import artifact_json
from resto.application.tools.network_author import (
    AuthorRun,
    NetworkCatalog,
    build_find_network_tool,
    build_network_author_tools,
)
from resto.application.tools.network_edit import EditRun, build_network_edit_tools
from resto.application.tools.network_import import ImportRun, build_network_import_tools
from resto.application.tools.network_inspection import (
    InspectionRun,
    build_network_inspection_tools,
)
from resto.domain.services.content_hash import short_hash
from resto.domain.value_objects.drafts import NetworkDraft, UnresolvedIssue
from resto.domain.value_objects.outcomes import NetworkOutcome
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask

# Bump whenever the prompt, the tool set or the default budget changes in a way that can change
# the agent's answers (E6.2 records it with every measurement).
NETWORK_AUTHOR_VERSION = "v7"

_COMMON = """\
You are the Network Author of a SUMO traffic-simulation framework. You make sure a road network
exists, and you never approximate: what you cannot do, you say.

How you work. Every tool that builds a network returns a `net_artifact` (path and content_hash) and
what the recipe needs (`source`, `osm_snapshot`, `netconvert_options`, `modification`). Never type a
path, a hash or a polygon yourself: use exactly what a tool returned. A round is one repair cycle:
change the network, recompile, then call `sanity_check` on the result. You have at most
`max_rounds` rounds; the number of tool calls is limited separately. Selecting, listing, locating
and verifying cost no round: only the repair cycle does, so try another selection before you give
up on one.

You finish by calling submit_output. A NetworkDraft is:
  - recipe: {source | base_network_id, osm_snapshot, netconvert_options, plain_edits}. It must
    replay without you and give the same `content_hash`: put in it exactly the source,
    snapshot, options and modifications the tools returned for the network you submit.
  - net_artifact: the `net_artifact` of the last tool that built the network you submit.
  - sanity_report: the numbers `sanity_check` returned for that same network (largest_scc_ratio,
    zero_length_edges, all_reachable_from_fringe).
  - probe_report: only if you called `probe_run` on it.
  - unresolved: every defect you found and did not fix, or every request you could not carry
    out, each with the `needed_tool` that was missing. If the sanity check still fails when you
    run out of rounds, submit the draft with the failure listed here; an empty list on a failing
    network is rejected.
  - rationale: what you decided and why, in one or two sentences.
"""

OBTAIN_PROMPT = (
    _COMMON
    + """
Your task: resolve `network_ref`, the way the user named the network. Start with
`find_network(name)`; `find_network` matches a label exactly, so pass the name of the network
alone, without what the user wants in it ("Eixample", not "Eixample with the train"). Then
choose exactly one ending:

  1. Found(id): one stored network is what the user means. Use the id `find_network` returned.
  2. A NetworkDraft: nothing stored matches and the network can be built. Build it:
       - "a 5 by 5 grid", a spider or a random network: `generate_grid`, `generate_spider` or
         `generate_random` (random needs a seed; pick one and keep it). Nothing else is needed.
       - a real area (a district, a box or a polygon): `list_import_profiles`, `fetch_osm`, then
         `netconvert` with the profile that keeps what the user asked for ("with the train" is
         the rail profile, "with bicycle lanes" the bicycle profile), then cleanups if the sanity
         check asks for them (`keep_largest_component`, `remove_isolated`, `join_junctions`,
         `keep_vclass`). A whole district or box needs nothing more.
       - only some streets ("the Diagonal from the Hospital Broggi to Francesc Macià"):
         `locate_place` every place the user named and draw the box from those points, a few
         hundred metres wider, never from memory; `fetch_osm` the box. For a street between
         two places, `trace_corridor` from one to the other and pass its
         `suggested_selection` to `select_streets` (if it answers `not_reached`, `fetch_osm`
         the box it gives and trace again); otherwise `list_streets` near a located point to
         see how the street is spelled and whether it changes name (then use its ref), and
         `select_streets`. Then `netconvert` the selected snapshot; `verify_coverage`.
         When the user wants a zone in detail (a municipality's accesses, a motorway link, a
         roundabout with everything that reaches it, a neighbourhood), `locate_place` its
         point, `list_streets` near it, and `select_streets` with that zone in `areas`; then
         `drop` by class (`residential`, `service`) and by name what is left over. Keep
         selecting by name, or tracing, for a long stretch. A zone keeps whole the ramps and
         roundabouts it touches: the radius does not have to be guessed to cover a complete ramp
         or roundabout. If `suggested_selection` has `areas`, pass them as they are, never
         replaced by a circle of your own; if you want more, add zones, do not remove the
         suggested ones. The entrances and exits of a municipality to a road
         are the link where the road reaches the municipality, not its centre: find it with
         `trace_corridor` or with a place of the request near it, never with the centre of the
         municipality. For example:
           select_streets(refs=["B-23"], areas=[{"near": [41.374, 2.0716], "radius_m": 500}],
                          drop=[{"classes": ["residential", "service"]}])
         A selection in more than one piece, a missing stretch or a place far from the
         network's ends means a selection to try again (other names, a ref, other
         connectors). What you cannot fix goes to unresolved[] with the numbers the coverage
         report gave.
  3. NeedsUser(reason, message, candidates): the user must act. Use it when
       - two or more stored networks match: SeveralCandidates, with their ids as candidates;
       - nothing is stored and it cannot be built from the reference: NetworkNotFound;
       - `fetch_osm` answered `needs_user` (area too large, place that is not an administrative
         boundary, unsupported requirement): pass its reason on as it is, and say what you were
         asked and why it cannot be done;
       - the user asks for something no profile imports (public transport stops or lines,
         polygons): UnsupportedRequirement. Do not build a network without it and say nothing.
"""
)

AUTHOR_PROMPT = (
    _COMMON
    + """
Your task: derive a new network from the base network `base_net` by carrying out `modifications`,
each in the order given, with `remove_edge`, `add_edge`, `set_lanes` and `set_speed`. Each edit tool
takes the `net_path` and `net_hash` of the network to edit and returns the edited one: chain them,
and put each returned `modification` in the recipe's plain_edits in that order. The recipe's
base_network_id is the task's `base_network_id`; it has no source and no osm_snapshot.

An edit a tool answers with `unresolved` (an edge that does not exist, a junction that does not
exist) is not carried out: copy that issue to the draft's unresolved. A modification for which no
tool exists (for example a new junction) goes to unresolved with the tool that is missing, never
approximated with another edit.
"""
)


@dataclass(frozen=True, slots=True)
class NetworkAuthorCollaborators:
    """Everything the Network Author's tools are bound to except the per-run state."""

    networks: NetworkRepository
    runner: NetconvertRunner
    editor: PlainNetEditor
    prober: NetworkProber
    open_network: Callable[[Path], EnumerableNetworkQuery]
    osm: OsmSource
    geocoder: Geocoder
    typemap_dir: Path
    out_dir: Path
    limits: OsmLimits = field(default_factory=OsmLimits)


def _task_input(task: ObtainNetworkTask | NetworkTask, limits: OsmLimits) -> dict[str, Any]:
    common: dict[str, Any] = {
        "goals": list(task.goals),
        "max_rounds": task.max_rounds,
        "min_scc_ratio": task.min_scc_ratio,
        "probe_teleport_threshold": task.probe_teleport_threshold,
    }
    if isinstance(task, ObtainNetworkTask):
        return {
            "network_ref": task.network_ref,
            "max_area_km2": limits.max_area_km2,
            **common,
        }
    return {
        "base_network_id": task.base_network_id,
        "modifications": [asdict(m) | {"kind": type(m).__name__} for m in task.modifications],
        **common,
    }


def _surface_service_errors(
    tools: Sequence[Tool], failures: list[ExternalServiceError]
) -> tuple[Tool, ...]:
    def guard(tool: Tool) -> Tool:
        def call(**kwargs: Any) -> Any:
            try:
                return tool.fn(**kwargs)
            except ExternalServiceError as error:
                failures.append(error)
                raise

        return replace(tool, fn=call)

    return tuple(guard(t) for t in tools)


@dataclass(slots=True)
class _Rounds:
    """The repair cycles one run has spent: each `sanity_check` call closes one."""

    limit: int
    spent: int = 0

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.limit


def _limit_rounds(tools: Sequence[Tool], rounds: _Rounds) -> tuple[Tool, ...]:
    def guard(tool: Tool) -> Tool:
        def call(**kwargs: Any) -> Any:
            if rounds.exhausted:
                raise RuntimeError(
                    f"the {rounds.limit} rounds are spent: call submit_output now with the "
                    "network you have, listing in unresolved[] what is still wrong"
                )
            result = tool.fn(**kwargs)
            if tool.name == "sanity_check":
                rounds.spent += 1
            return result

        return replace(tool, fn=call)

    return tuple(guard(t) for t in tools)


def _report_exhaustion(run: AgentRun[Any], rounds: _Rounds, min_scc_ratio: float) -> AgentRun[Any]:
    """A draft that spent every round and still fails the sanity check says so in `unresolved[]`,
    whatever the model wrote there."""
    draft = run.output
    if not (
        isinstance(draft, NetworkDraft)
        and rounds.exhausted
        and draft.is_silent_failure(min_scc_ratio)
    ):
        return run
    issue = UnresolvedIssue(
        "edge",
        "*",
        f"the {rounds.limit} rounds were spent and the sanity check still fails "
        f"({draft.sanity_report})",
    )
    return replace(run, output=replace(draft, unresolved=(issue,)))


@dataclass(frozen=True, slots=True)
class NetworkAuthorPort:
    """`NetworkAuthorAgent` port (ADR-0025 §6) over the shared `ToolAgent`, with the collaborators
    bound. `budget` limits the calls of one run."""

    agent: ToolAgent
    budget: Budget
    collaborators: NetworkAuthorCollaborators

    def obtain(self, task: ObtainNetworkTask) -> AgentRun[NetworkOutcome]:
        c = self.collaborators
        tools = (
            build_find_network_tool(NetworkCatalog(c.networks)),
            *build_network_author_tools(AuthorRun(c.runner, self._work_dir)),
            *build_network_import_tools(
                ImportRun(
                    runner=c.runner,
                    osm=c.osm,
                    geocoder=c.geocoder,
                    out_dir=self._work_dir,
                    typemap_dir=c.typemap_dir,
                    limits=c.limits,
                )
            ),
            *build_network_inspection_tools(self._inspection()),
        )
        agent_task = AgentTask(OBTAIN_PROMPT, _task_input(task, c.limits))
        # a union is not a `type[T]` for mypy; the real client builds its schema from it anyway
        return self._run(agent_task, tools, cast("type[NetworkOutcome]", NetworkOutcome), task)

    def author(self, task: NetworkTask) -> AgentRun[NetworkDraft]:
        c = self.collaborators
        base = c.networks.get(task.base_network_id)
        if base is None:
            raise NetworkNotStored(f"base network {task.base_network_id!r} is not stored")
        tools = (
            *build_network_edit_tools(EditRun(c.runner, c.editor, self._work_dir)),
            *build_network_inspection_tools(self._inspection()),
        )
        agent_input = _task_input(task, c.limits)
        # the inspection tools read only inside the working directory, so the agent gets a copy
        shown = (
            self._work_dir / "base" / short_hash(base.net_xml.content_hash) / base.net_xml.path.name
        )
        shown.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base.net_xml.path, shown)
        agent_input["base_net"] = artifact_json(replace(base.net_xml, path=shown))
        return self._run(AgentTask(AUTHOR_PROMPT, agent_input), tools, NetworkDraft, task)

    @property
    def _work_dir(self) -> Path:
        return self.collaborators.out_dir

    def _inspection(self) -> InspectionRun:
        c = self.collaborators
        return InspectionRun(open_network=c.open_network, prober=c.prober, out_dir=self._work_dir)

    def _run(
        self,
        agent_task: AgentTask,
        tools: Sequence[Tool],
        output: type[Any],
        task: ObtainNetworkTask | NetworkTask,
    ) -> AgentRun[Any]:
        failures: list[ExternalServiceError] = []
        rounds = _Rounds(task.max_rounds)
        guarded = _limit_rounds(_surface_service_errors(tools, failures), rounds)
        run = self.agent.run(agent_task, guarded, output, self.budget)
        if failures:
            raise failures[0]
        return _report_exhaustion(run, rounds, task.min_scc_ratio)
