"""The `obtain_network` and `derive_network` steps with a scripted `ToolAgent` (E6.1/07; ADR-0037,
ADR-0045). The tools, `netconvert`, `netgenerate`, the promoter and its replay are real (SUMO
1.27.1); only the `OsmSource`, the geocoder and the model are replaced. What is checked is what the
study shows: the network it ends with, the `NeedsUser` it waits on, the step that failed and why.
The agent's own judgement is not under test: each script plays one decision of it."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sumolib.net

from resto.adapters.llm.agents.network_author import NetworkAuthorCollaborators, NetworkAuthorPort
from resto.adapters.persistence.memory import InMemoryNetworkRepository
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.network_probe import SumoNetworkProber
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.osm_map import NetEdge
from resto.application.ports.llm import AgentTask, Budget, Tool
from resto.application.ports.network_query import NetworkNotStored
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.application.ports.repositories import NetworkRepository
from resto.application.promoters.network import NetworkPromoter
from resto.application.run_study.steps.derive_network import DeriveNetworkExecutor
from resto.application.run_study.steps.obtain_network import ObtainNetworkExecutor
from resto.domain.entities.network import Network
from resto.domain.entities.study import Study, StudyResolution
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.drafts import NetworkDraft, UnresolvedIssue
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import (
    BBox,
    GeneratedNetwork,
    GridNetwork,
    Polygon,
    RandomNetwork,
    SpiderNetwork,
)
from resto.domain.value_objects.outcomes import (
    AreaTooLarge,
    Found,
    NeedsUser,
    NetworkNotFound,
    PlaceNotBoundary,
    SeveralCandidates,
    UnsupportedRequirement,
)
from resto.domain.value_objects.probe_report import ProbeReport
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.step_record import StepErrorKind, StepStatus
from resto.domain.value_objects.study_plan import (
    DeriveNetworkStep,
    FromStep,
    ObtainNetworkStep,
    StudyPlan,
)
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
    TopologyModification,
)
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.application._world import DESCRIBE, World, answers
from tests.unit.application.run_study.test_obtain_steps import NETWORK_ONLY, _obtain_plan
from tests.unit.application.tools._osm_doubles import (
    CORRIDOR_OSM,
    DISTRICT,
    EAST_END,
    WEST_END,
    FakeGeocoder,
    FakeOsmSource,
)
from tests.unit.domain._fixtures import NET, bad_sanity

RUNNER = SubprocessNetconvertRunner()
RING = [list(point) for point in DISTRICT.ring]
Script = Callable[[AgentTask, Sequence[Tool]], Any]


# -- the world around the port --------------------------------------------------------------


class Setup:
    """One study through `RunStudy` whose network steps use the real Network Author tools."""

    def __init__(
        self,
        tmp_path: Path,
        script: Script,
        *,
        plan: StudyPlan,
        osm: Any = None,
        geocoder: Any = None,
        limits: OsmLimits | None = None,
        stored: Sequence[Network] = (),
        question: Question = NETWORK_ONLY,
        derive_from: NetworkRepository | None = None,
    ) -> None:
        self._derive_from = derive_from
        self.osm = osm or FakeOsmSource()
        self.world = World(
            tmp_path / "world", plans=(plan,), question=question, expert=(answers(),)
        )
        for network in stored:
            self.world.networks.store(network)
        fake = FakeToolAgent(output=None)

        def interact(task: AgentTask, tools: Sequence[Tool]) -> None:
            fake.output = script(task, tools)

        fake.interact = interact
        self.agent = NetworkAuthorPort(
            fake,
            Budget(40, 4096, 300.0),
            NetworkAuthorCollaborators(
                networks=self.world.networks,
                runner=RUNNER,
                editor=XmlPlainNetEditor(),
                prober=SumoNetworkProber(SubprocessSumoRunner()),
                open_network=SumolibNetworkQuery,
                osm=self.osm,
                geocoder=geocoder or FakeGeocoder(),
                typemap_dir=typemap_dir(),
                out_dir=tmp_path / "author",
                limits=limits or OsmLimits(),
            ),
        )

    def run(self) -> Study:
        promoter = NetworkPromoter(RUNNER, XmlPlainNetEditor())
        run_study = self.world.run_study()
        steps = {
            **run_study.steps,
            ObtainNetworkStep: ObtainNetworkExecutor(self.agent, self.world.networks, promoter, 5),
            DeriveNetworkStep: DeriveNetworkExecutor(
                self.agent, self._derive_from or self.world.networks, promoter, 5
            ),
        }
        return replace(run_study, steps=steps).execute("the user's text")


def obtain_plan(ref: str = "RIVERSIDE") -> StudyPlan:
    return StudyPlan(
        network_id=FromStep(0), rationale="network only", steps=(ObtainNetworkStep(ref),)
    )


def derive_plan(ref: str, *modifications: TopologyModification) -> StudyPlan:
    """Resolve `ref` (a plan always starts with `obtain_network`), then derive from it."""
    return StudyPlan(
        network_id=FromStep(1),
        rationale="derive",
        steps=(
            ObtainNetworkStep(ref),
            DeriveNetworkStep(FromStep(0), modifications, depends_on=(0,)),
        ),
    )


def after_finding(derive: Script) -> Script:
    """Find the stored base by its label, then play `derive` on the derivation step."""

    def play(task: AgentTask, tools: Sequence[Tool]) -> Any:
        if "network_ref" in task.input:
            return resolve_by_label(task, tools)
        return derive(task, tools)

    return play


# -- what a scripted agent builds from tool results --------------------------------------------


def ref(artifact: Mapping[str, Any]) -> ArtifactRef:
    return ArtifactRef(Path(artifact["path"]), artifact["content_hash"], artifact["kind"])


def sanity_of(tools: Sequence[Tool], artifact: Mapping[str, Any]) -> SanityReport:
    report = call_tool(tools, "sanity_check", net_path=artifact["path"])
    return SanityReport(
        report["largest_scc_ratio"],
        report["zero_length_edges"],
        report["all_reachable_from_fringe"],
    )


def draft_of(
    recipe: NetworkRecipe,
    tools: Sequence[Tool],
    artifact: Mapping[str, Any],
    *,
    sanity: SanityReport | None = None,
    unresolved: tuple[UnresolvedIssue, ...] = (),
    probe: ProbeReport | None = None,
) -> NetworkDraft:
    return NetworkDraft(
        recipe=recipe,
        net_artifact=ref(artifact),
        sanity_report=sanity or sanity_of(tools, artifact),
        rationale="built it with the tools",
        probe_report=probe,
        unresolved=unresolved,
    )


def grid_script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
    built = call_tool(tools, "generate_grid", x_number=3, y_number=3)
    return draft_of(NetworkRecipe(source=GridNetwork(3, 3)), tools, built["net_artifact"])


def import_script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
    fetched = call_tool(tools, "fetch_osm", polygon=RING)
    snapshot = fetched["osm_snapshot"]
    built = call_tool(tools, "netconvert", osm_snapshot=snapshot["content_hash"])
    recipe = NetworkRecipe(
        source=Polygon(ring=tuple(fetched["source"]["ring"])),
        osm_snapshot=ref(snapshot),
        netconvert_options=tuple(built["netconvert_options"]),
    )
    return draft_of(recipe, tools, built["net_artifact"])


def resolve_by_label(task: AgentTask, tools: Sequence[Tool]) -> Found | NeedsUser:
    """The agent's decision on stored networks: one match is `Found`, several are a question and
    none is a `NetworkNotFound`."""
    name = task.input["network_ref"]
    candidates = call_tool(tools, "find_network", name=name)["candidates"]
    ids = tuple(c["network_id"] for c in candidates)
    if len(ids) == 1:
        return Found(ids[0])
    if ids:
        return NeedsUser(SeveralCandidates(), f"{name!r} matches several networks", ids)
    return NeedsUser(NetworkNotFound(name), f"no stored network is called {name!r}")


def needs_user_of(result: Mapping[str, Any]) -> NeedsUser:
    """The `NeedsUser` an agent builds from the `needs_user` a tool returned."""
    reasons: dict[str, Callable[..., Any]] = {
        "network_not_found": NetworkNotFound,
        "place_not_boundary": PlaceNotBoundary,
        "area_too_large": AreaTooLarge,
        "unsupported_requirement": UnsupportedRequirement,
    }
    needs = result["needs_user"]
    reason = reasons[needs["reason"]["kind"]](**needs["reason"])
    return NeedsUser(reason, needs["message"], tuple(needs["candidates"]))


def swallowing(script: Script) -> Script:
    """What the real `ToolAgent` does with a failing tool: it tells the model and goes on."""

    def play(task: AgentTask, tools: Sequence[Tool]) -> Any:
        try:
            return script(task, tools)
        except Exception as error:
            return NeedsUser(NetworkNotFound("x"), f"a tool failed: {error}")

    return play


# -- stored networks ---------------------------------------------------------------------------


def stored_grid(tmp_path: Path, size: int, label: str) -> Network:
    built = RUNNER.generate(GridNetwork(size, size), tmp_path / f"stored-{size}")
    return Network(
        network_id=built.content_hash,
        net_xml=built,
        recipe=NetworkRecipe(source=GridNetwork(size, size)),
        sanity_report=SanityReport(1.0, 0, True),
        label=label,
    )


def test_a_stored_network_that_matches_the_name_is_found(tmp_path: Path) -> None:
    riverside = stored_grid(tmp_path, 3, "riverside")
    setup = Setup(tmp_path, resolve_by_label, plan=obtain_plan(), stored=[riverside])

    study = setup.run()

    assert study.resolution is StudyResolution.COMPLETED
    assert study.network_ids == (riverside.network_id,)
    assert {n.network_id for n in setup.world.networks.list()} == {NET, riverside.network_id}


def test_two_stored_networks_that_match_ask_the_user_which_one(tmp_path: Path) -> None:
    south, north = (
        stored_grid(tmp_path, 3, "riverside"),
        stored_grid(tmp_path, 4, "Riverside"),
    )
    setup = Setup(tmp_path, resolve_by_label, plan=obtain_plan(), stored=[south, north])

    study = setup.run()

    assert study.resolution is StudyResolution.AWAITING_USER
    needs = study.phases[0].needs_user
    assert isinstance(needs, NeedsUser) and isinstance(needs.reason, SeveralCandidates)
    assert set(needs.candidates) == {south.network_id, north.network_id}


def test_a_name_with_no_match_is_network_not_found(tmp_path: Path) -> None:
    setup = Setup(tmp_path, resolve_by_label, plan=obtain_plan("Atlantis"))

    study = setup.run()

    assert study.resolution is StudyResolution.AWAITING_USER
    needs = study.phases[0].needs_user
    assert isinstance(needs, NeedsUser) and needs.reason == NetworkNotFound("Atlantis")
    assert setup.osm.calls == []


# -- generated networks ------------------------------------------------------------------------

GENERATED = [
    pytest.param("generate_grid", {"x_number": 3, "y_number": 2}, GridNetwork(3, 2), id="grid"),
    pytest.param(
        "generate_spider",
        {"arm_number": 4, "circle_number": 2},
        SpiderNetwork(arm_number=4, circle_number=2),
        id="spider",
    ),
    pytest.param(
        "generate_random",
        {"seed": 5, "iterations": 15},
        RandomNetwork(seed=5, iterations=15),
        id="random",
    ),
]


@pytest.mark.parametrize(("tool", "arguments", "source"), GENERATED)
def test_a_generated_network_is_promoted_with_a_recipe_that_replays_to_its_hash(
    tmp_path: Path, tool: str, arguments: dict[str, Any], source: GeneratedNetwork
) -> None:
    built: dict[str, Any] = {}

    def script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
        built.update(call_tool(tools, tool, **arguments))
        return draft_of(NetworkRecipe(source=source), tools, built["net_artifact"])

    setup = Setup(tmp_path, script, plan=obtain_plan("a generated one"))

    study = setup.run()

    assert study.resolution is StudyResolution.COMPLETED
    (network_id,) = study.network_ids
    promoted = setup.world.networks.get(network_id)
    assert promoted is not None
    assert network_id == built["net_artifact"]["content_hash"]  # promotion replayed the recipe
    assert promoted.recipe.source == source
    assert sumolib.net.readNet(str(promoted.net_xml.path)).getEdges()


def test_the_demand_generator_receives_the_id_of_the_network_that_was_built(
    tmp_path: Path,
) -> None:
    setup = Setup(
        tmp_path, grid_script, plan=_obtain_plan(network_ref="a 3 by 3 grid"), question=DESCRIBE
    )

    study = setup.run()

    (network_id, *_) = study.network_ids
    assert network_id not in {NET}
    task = setup.world.generator.calls[0][0]
    assert task.network_id == network_id


def test_an_obtained_network_is_found_by_the_name_it_was_asked_for(tmp_path: Path) -> None:
    first = Setup(tmp_path, grid_script, plan=obtain_plan("a 3 by 3 grid"))
    study = first.run()
    (network_id,) = study.network_ids

    again = Setup(
        tmp_path / "later",
        resolve_by_label,
        plan=obtain_plan("a 3 by 3 grid"),
        stored=list(first.world.networks.list()),
    )
    later = again.run()

    assert later.resolution is StudyResolution.COMPLETED
    assert later.network_ids == (network_id,)


# -- areas of interest -------------------------------------------------------------------------


def test_an_area_of_interest_is_imported_and_a_second_request_downloads_nothing(
    tmp_path: Path,
) -> None:
    osm = FakeOsmSource()

    study = Setup(tmp_path, import_script, plan=obtain_plan("the district"), osm=osm).run()
    again = Setup(tmp_path, import_script, plan=obtain_plan("the district"), osm=osm).run()

    assert study.resolution is StudyResolution.COMPLETED
    assert again.resolution is StudyResolution.COMPLETED
    assert again.network_ids == study.network_ids
    assert len(osm.calls) == 2 and osm.downloads == 1


def test_an_area_above_the_limit_asks_the_user_before_any_download(tmp_path: Path) -> None:
    def script(task: AgentTask, tools: Sequence[Tool]) -> NeedsUser:
        return needs_user_of(call_tool(tools, "fetch_osm", bbox=[41.0, 2.0, 41.5, 2.5]))

    setup = Setup(tmp_path, script, plan=obtain_plan("Barcelona"))

    study = setup.run()

    assert study.resolution is StudyResolution.AWAITING_USER
    needs = study.phases[0].needs_user
    assert isinstance(needs, NeedsUser) and isinstance(needs.reason, AreaTooLarge)
    assert needs.reason.limit_km2 == OsmLimits().max_area_km2
    assert setup.osm.calls == []


def test_a_place_that_is_not_a_boundary_asks_the_user_and_downloads_nothing(
    tmp_path: Path,
) -> None:
    def script(task: AgentTask, tools: Sequence[Tool]) -> NeedsUser:
        return needs_user_of(call_tool(tools, "fetch_osm", place_name="Plaça Catalunya"))

    geocoder = FakeGeocoder(rejection="it is a point, not an administrative boundary")
    setup = Setup(tmp_path, script, plan=obtain_plan("Plaça Catalunya"), geocoder=geocoder)

    study = setup.run()

    assert study.resolution is StudyResolution.AWAITING_USER
    needs = study.phases[0].needs_user
    assert isinstance(needs, NeedsUser) and isinstance(needs.reason, PlaceNotBoundary)
    assert "point" in needs.message
    assert geocoder.queries == ["Plaça Catalunya"] and setup.osm.calls == []


def test_a_requirement_the_network_cannot_hold_asks_the_user_and_downloads_nothing(
    tmp_path: Path,
) -> None:
    def script(task: AgentTask, tools: Sequence[Tool]) -> NeedsUser:
        return needs_user_of(
            call_tool(tools, "fetch_osm", polygon=RING, requirements=["bus stops"])
        )

    setup = Setup(tmp_path, script, plan=obtain_plan("the district with bus stops"))

    study = setup.run()

    assert study.resolution is StudyResolution.AWAITING_USER
    needs = study.phases[0].needs_user
    assert isinstance(needs, NeedsUser) and isinstance(needs.reason, UnsupportedRequirement)
    assert setup.osm.calls == []


def corridor_script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
    """The Diagonal from the hospital to the square: locate both, download a box around them,
    look at the streets, select the road by name and by ref, build it and check the coverage."""
    west = call_tool(tools, "locate_place", query=WEST_END.query)
    east = call_tool(tools, "locate_place", query=EAST_END.query)
    margin = 0.005
    box = [
        min(west["lat"], east["lat"]) - margin,
        min(west["lon"], east["lon"]) - margin,
        max(west["lat"], east["lat"]) + margin,
        max(west["lon"], east["lon"]) + margin,
    ]
    fetched = call_tool(tools, "fetch_osm", bbox=box)
    downloaded = fetched["osm_snapshot"]["content_hash"]
    streets = call_tool(
        tools, "list_streets", osm_snapshot=downloaded, near=[west["lat"], west["lon"]]
    )
    assert {s["ref"] for s in streets["streets"]} >= {"N-340"}
    selected = call_tool(
        tools, "select_streets", osm_snapshot=downloaded, names=["Diagonal"], refs=["N-340"]
    )
    snapshot = selected["osm_snapshot"]
    built = call_tool(tools, "netconvert", osm_snapshot=snapshot["content_hash"])
    coverage = call_tool(tools, "verify_coverage", osm_snapshot=snapshot["content_hash"])
    assert coverage["streets_with_missing_stretches"] == []
    assert all(p["to_nearest_end_m"] < 50 for p in coverage["places"])
    recipe = NetworkRecipe(
        source=BBox(**{k: v for k, v in selected["source"].items() if k != "kind"}),
        osm_snapshot=ref(snapshot),
        netconvert_options=tuple(built["netconvert_options"]),
    )
    return draft_of(recipe, tools, built["net_artifact"])


def test_a_corridor_is_located_selected_verified_and_promoted_from_its_selection(
    tmp_path: Path,
) -> None:
    osm = FakeOsmSource(CORRIDOR_OSM)
    setup = Setup(
        tmp_path,
        corridor_script,
        plan=obtain_plan("the Diagonal from the Hospital Broggi to Francesc Macia"),
        osm=osm,
        geocoder=FakeGeocoder(places=(WEST_END, EAST_END)),
    )

    study = setup.run()

    assert study.resolution is StudyResolution.COMPLETED
    (network_id,) = study.network_ids
    promoted = setup.world.networks.get(network_id)
    assert promoted is not None and promoted.recipe.osm_snapshot is not None
    assert promoted.recipe.osm_snapshot.path.name.startswith("selected-")
    ways = {w for edge in NetEdge.read_all(promoted.net_xml.path) for w in edge.osm_ways}
    assert ways == {300, 301, 302, 303, 304}, "the road, its link and its square; no cross street"
    assert osm.downloads == 1
    assert isinstance(promoted.recipe.source, BBox), "the box drawn from the located places"
    assert promoted.recipe.source.west == pytest.approx(WEST_END.lon - 0.005)
    assert promoted.recipe.source.east == pytest.approx(EAST_END.lon + 0.005)


class DownOsm:
    calls: list[object] = []

    def fetch(self, area: object, out_dir: Path) -> ArtifactRef:
        raise ExternalServiceError("overpass", "HTTP 504")


@pytest.mark.parametrize(
    ("service", "osm", "geocoder"),
    [
        pytest.param("nominatim", None, FakeGeocoder(down=True), id="geocoder"),
        pytest.param("overpass", DownOsm(), None, id="overpass"),
    ],
)
@pytest.mark.parametrize("swallows", [False, True], ids=["raises", "model-keeps-going"])
def test_a_service_that_fails_fails_the_step_by_its_name(
    tmp_path: Path, service: str, osm: Any, geocoder: Any, swallows: bool
) -> None:
    def script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
        call_tool(tools, "fetch_osm", place_name="Sant Antoni")
        raise AssertionError("fetch_osm must not succeed")

    setup = Setup(
        tmp_path,
        swallowing(script) if swallows else script,
        plan=obtain_plan("Sant Antoni"),
        osm=osm,
        geocoder=geocoder,
    )

    study = setup.run()

    assert study.resolution is StudyResolution.FAILED
    failed = study.phases[0].failed_step
    assert failed is not None and failed.tool == "obtain_network"
    assert failed.status is StepStatus.FAILED and failed.error is not None
    assert service in failed.error.message


# -- promotion refuses ------------------------------------------------------------------------


def sanity_failing_grid(unresolved: tuple[UnresolvedIssue, ...]) -> Script:
    def script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
        built = call_tool(tools, "generate_grid", x_number=3, y_number=3)
        return draft_of(
            NetworkRecipe(source=GridNetwork(3, 3)),
            tools,
            built["net_artifact"],
            sanity=bad_sanity(),
            unresolved=unresolved,
        )

    return script


def test_rounds_spent_with_the_sanity_failing_leave_a_draft_that_says_so(tmp_path: Path) -> None:
    issue = UnresolvedIssue("edge", "A0A1", "still cut off from the border", None)
    setup = Setup(tmp_path, sanity_failing_grid((issue,)), plan=obtain_plan("a grid"))

    study = setup.run()

    assert study.resolution is StudyResolution.COMPLETED
    (network_id,) = study.network_ids
    promoted = setup.world.networks.get(network_id)
    assert promoted is not None and not promoted.sanity_report.passes()


def test_the_round_limit_is_imposed_and_a_draft_still_failing_then_says_so(tmp_path: Path) -> None:
    refused: list[str] = []

    def script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
        built = call_tool(tools, "generate_grid", x_number=3, y_number=3)
        call_tool(tools, "sanity_check", net_path=built["net_artifact"]["path"])  # round 1
        call_tool(tools, "sanity_check", net_path=built["net_artifact"]["path"])  # round 2
        with pytest.raises(RuntimeError, match="rounds are spent") as spent:
            call_tool(tools, "generate_grid", x_number=4, y_number=4)
        refused.append(str(spent.value))
        return draft_of(
            NetworkRecipe(source=GridNetwork(3, 3)),
            tools=(),
            artifact=built["net_artifact"],
            sanity=bad_sanity(),
        )

    setup = Setup(tmp_path, script, plan=obtain_plan("a grid"))

    run = setup.agent.obtain(ObtainNetworkTask("a grid", max_rounds=2))

    assert refused
    assert isinstance(run.output, NetworkDraft)
    assert run.output.unresolved and "2 rounds" in run.output.unresolved[0].issue


def test_a_run_inside_its_rounds_is_left_as_the_agent_wrote_it(tmp_path: Path) -> None:
    setup = Setup(tmp_path, grid_script, plan=obtain_plan("a grid"))

    run = setup.agent.obtain(ObtainNetworkTask("a grid", max_rounds=2))

    assert isinstance(run.output, NetworkDraft) and run.output.unresolved == ()


# -- derivation --------------------------------------------------------------------------------

BASE_GRID = GridNetwork(3, 3)
EDITS = [
    pytest.param("remove_edge", {"edge_id": "A0A1"}, RemoveEdge("A0A1"), id="remove_edge"),
    pytest.param("set_lanes", {"edge_id": "A0A1", "lanes": 2}, SetLanes("A0A1", 2), id="set_lanes"),
    pytest.param(
        "set_speed", {"edge_id": "A0A1", "speed": 8.0}, SetSpeed("A0A1", 8.0), id="set_speed"
    ),
    pytest.param(
        "add_edge",
        {
            "from_junction": "A0",
            "to_junction": "B1",
            "lanes": 1,
            "speed": 13.9,
            "edge_id": "A0B1new",
        },
        AddEdge("A0", "B1", lanes=1, speed=13.9, edge_id="A0B1new"),
        id="add_edge",
    ),
]


def derive_script(
    tool: str, arguments: dict[str, Any], modification: TopologyModification
) -> Script:
    def script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
        base = task.input["base_net"]
        edited = call_tool(
            tools, tool, net_path=base["path"], net_hash=base["content_hash"], **arguments
        )
        recipe = NetworkRecipe(
            base_network_id=task.input["base_network_id"], plain_edits=(modification,)
        )
        return draft_of(recipe, tools, edited["net_artifact"])

    return script


@pytest.mark.parametrize(("tool", "arguments", "modification"), EDITS)
def test_each_edit_derives_a_network_that_points_at_its_base(
    tmp_path: Path, tool: str, arguments: dict[str, Any], modification: TopologyModification
) -> None:
    base = stored_grid(tmp_path, 3, "base")
    setup = Setup(
        tmp_path,
        after_finding(derive_script(tool, arguments, modification)),
        plan=derive_plan("base", modification),
        stored=[base],
    )

    study = setup.run()

    assert study.resolution is StudyResolution.COMPLETED
    assert study.network_ids[0] == base.network_id
    network_id = study.network_ids[-1]
    derived = setup.world.networks.get(network_id)
    assert derived is not None
    assert derived.derived_from == base.network_id and network_id != base.network_id
    assert derived.recipe.plain_edits == (modification,)
    edges = {e.getID() for e in sumolib.net.readNet(str(derived.net_xml.path)).getEdges()}
    assert ("A0A1" in edges) is (tool != "remove_edge")


def test_a_base_network_that_is_not_stored_is_a_typed_error_of_the_port(tmp_path: Path) -> None:
    setup = Setup(tmp_path, grid_script, plan=obtain_plan())

    with pytest.raises(NetworkNotStored, match="ghost"):
        setup.agent.author(NetworkTask("ghost", max_rounds=5))


def test_a_derivation_whose_base_is_not_stored_fails_before_the_agent_is_called(
    tmp_path: Path,
) -> None:
    base = stored_grid(tmp_path, 3, "base")
    calls: list[AgentTask] = []

    def script(task: AgentTask, tools: Sequence[Tool]) -> Any:
        calls.append(task)
        if "network_ref" in task.input:
            return resolve_by_label(task, tools)
        raise AssertionError("the derivation must not reach the agent")

    setup = Setup(
        tmp_path,
        script,
        plan=derive_plan("base", AddEdge("A0", "Z9", lanes=1, speed=13.9)),
        stored=[base],
        derive_from=InMemoryNetworkRepository(),
    )

    study = setup.run()

    assert study.resolution is StudyResolution.FAILED
    failed = study.phases[0].failed_step
    assert failed is not None and failed.tool == "derive_network"
    assert failed.error is not None and failed.error.kind is StepErrorKind.INFRASTRUCTURE
    assert base.network_id in failed.error.message
    assert len(calls) == 1


def test_an_edit_that_needs_a_junction_lists_the_tool_the_tool_that_was_missing(
    tmp_path: Path,
) -> None:
    base = stored_grid(tmp_path, 3, "base")
    modification = AddEdge("A0", "Z9", lanes=1, speed=13.9)

    def script(task: AgentTask, tools: Sequence[Tool]) -> NetworkDraft:
        shown = task.input["base_net"]
        result = call_tool(
            tools,
            "add_edge",
            net_path=shown["path"],
            net_hash=shown["content_hash"],
            from_junction="A0",
            to_junction="Z9",
            lanes=1,
            speed=13.9,
        )
        return draft_of(
            NetworkRecipe(base_network_id=base.network_id),
            tools,
            shown,
            unresolved=(UnresolvedIssue(**result["unresolved"]),),
        )

    setup = Setup(
        tmp_path,
        script,
        plan=derive_plan("base", modification),
        stored=[base],
    )
    task = NetworkTask(base.network_id, max_rounds=5, modifications=(modification,))

    run = setup.agent.author(task)

    assert run.output is not None
    assert [(u.element_id, u.needed_tool) for u in run.output.unresolved] == [("Z9", "add_node")]
