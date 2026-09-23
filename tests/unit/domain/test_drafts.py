from dataclasses import fields

import pytest

from resto.domain.entities.scenario import Scenario
from resto.domain.value_objects.calibration_round import CalibrationRound
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.drafts import (
    DemandDraft,
    ExpertNoteDraft,
    ExpertNoteDrafts,
    NetworkDraft,
    RejectedIntervention,
    ScenarioDraft,
    UnresolvedIssue,
)
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism, ScriptMechanism
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.tasks import NoteScenario, NoteTask
from tests.unit.domain._fixtures import (
    artifact,
    bad_sanity,
    demand_draft,
    dynamic_intervention,
    fidelity,
    good_sanity,
    network_draft,
    runnable_script,
    scenario_draft,
    static_intervention,
    unlinted_script,
)
from tests.unit.domain._samples import expert_answer

DRAFTS = (NetworkDraft, DemandDraft, ScenarioDraft, ExpertNoteDraft, ExpertNoteDrafts)
FORBIDDEN = ("_id", "content_hash", "status", "provenance")


@pytest.mark.parametrize("draft_type", DRAFTS)
def test_no_draft_can_carry_identity_or_provenance(draft_type: type) -> None:
    """Architecture §2.2: ids, hashes, status and provenance are the promotion step's to write."""
    names = [f.name for f in fields(draft_type)]
    assert not [n for n in names if any(n.endswith(suffix) for suffix in FORBIDDEN)]


@pytest.mark.parametrize("builder", [network_draft, demand_draft, scenario_draft])
def test_authoring_drafts_require_a_rationale(builder) -> None:
    with pytest.raises(ValueError):
        builder(rationale="   ")


def test_network_draft_rejects_an_artifact_that_is_not_a_net_xml() -> None:
    with pytest.raises(ValueError):
        network_draft(net_artifact=artifact("dev-net.osm", "abc123", "osm"))


def test_failing_sanity_without_unresolved_is_a_silent_failure() -> None:
    draft = network_draft(sanity_report=bad_sanity())
    assert draft.is_silent_failure()


def test_reporting_what_it_could_not_fix_is_not_a_silent_failure() -> None:
    draft = network_draft(
        sanity_report=bad_sanity(),
        unresolved=(
            UnresolvedIssue(
                element_kind="junction",
                element_id="J7",
                issue="turn lanes point the wrong way",
                needed_tool="set_connection",
            ),
        ),
    )
    assert not draft.is_silent_failure()


def test_passing_sanity_is_never_a_silent_failure() -> None:
    assert not network_draft().is_silent_failure()


def test_silent_failure_honours_the_threshold_the_task_asked_for() -> None:
    """A task may loosen min_scc_ratio; the draft must be judged against that, not the default."""
    draft = network_draft(
        sanity_report=type(good_sanity())(
            largest_scc_ratio=0.90, zero_length_edges=0, all_reachable_from_fringe=True
        )
    )
    assert draft.is_silent_failure()
    assert not draft.is_silent_failure(min_scc_ratio=0.85)


def test_unresolved_issue_must_name_the_element_and_the_defect() -> None:
    with pytest.raises(ValueError):
        UnresolvedIssue(element_kind="edge", element_id="", issue="broken")
    with pytest.raises(ValueError):
        UnresolvedIssue(element_kind="edge", element_id="E1", issue="  ")


def test_demand_draft_rejects_out_of_order_calibration_rounds() -> None:
    with pytest.raises(ValueError):
        demand_draft(
            calibration_rounds=(
                CalibrationRound(round=2, max_relative_error=0.2),
                CalibrationRound(round=1, max_relative_error=0.4),
            )
        )


def test_demand_draft_rejects_fidelity_with_no_calibration_behind_it() -> None:
    with pytest.raises(ValueError):
        demand_draft(fidelity=fidelity())


def test_demand_draft_accepts_fidelity_backed_by_rounds() -> None:
    draft = demand_draft(
        fidelity=fidelity(),
        calibration_rounds=(CalibrationRound(round=1, max_relative_error=0.05),),
    )
    assert draft.fidelity is not None


def test_scenario_draft_enforces_the_same_pairing_rule_as_the_entity() -> None:
    with pytest.raises(ValueError):
        scenario_draft(
            interventions=(dynamic_intervention(),),
            mechanisms=(RegenerateDemandMechanism(demand_id="d2"),),
        )


def test_scenario_draft_requires_a_script_for_script_mechanisms() -> None:
    with pytest.raises(ValueError):
        scenario_draft(
            interventions=(dynamic_intervention(),), mechanisms=(ScriptMechanism(),), script=None
        )


def test_a_draft_may_carry_a_script_that_failed_lint_but_a_scenario_may_not() -> None:
    """The draft reports what the agent built; promotion is what gates on lint and dry_run."""
    draft = scenario_draft(
        interventions=(dynamic_intervention(),),
        mechanisms=(ScriptMechanism(),),
        script=unlinted_script(),
    )
    assert draft.script is not None and not draft.script.is_runnable

    with pytest.raises(ValueError):
        Scenario(
            scenario_id="s1",
            network_id="n1",
            demand_id="d1",
            interventions=draft.interventions,
            mechanisms=draft.mechanisms,
            sumocfg=draft.sumocfg,
            content_hash="c1",
            traci_script=draft.script,
        )


def test_rejected_intervention_must_say_why() -> None:
    with pytest.raises(ValueError):
        RejectedIntervention(intervention=static_intervention(), reason="")


def test_scenario_draft_keeps_what_it_could_not_implement() -> None:
    draft = scenario_draft(
        rejected=(
            RejectedIntervention(
                intervention=dynamic_intervention(),
                reason="dynamic demand_scale is not supported in v1",
            ),
        )
    )
    assert draft.rejected[0].reason


def test_expert_note_draft_requires_evidence_when_it_claims_to_have_observed() -> None:
    with pytest.raises(ValueError):
        ExpertNoteDraft(text="E12 saturates at peak", basis=Basis.OBSERVED)


def test_an_extrapolated_note_may_stand_without_evidence() -> None:
    note = ExpertNoteDraft(text="a similar merge would saturate too", basis=Basis.EXTRAPOLATED)
    assert note.basis is Basis.EXTRAPOLATED


def test_expert_note_draft_requires_text() -> None:
    with pytest.raises(ValueError):
        ExpertNoteDraft(
            text="  ",
            basis=Basis.OBSERVED,
            evidence=(Evidence(kind=EvidenceKind.ARTIFACT, ref="edgedata.xml"),),
        )


def test_runnable_script_is_accepted_by_both_draft_and_entity() -> None:
    draft = scenario_draft(
        interventions=(dynamic_intervention(),),
        mechanisms=(ScriptMechanism(),),
        script=runnable_script(),
    )
    scenario = Scenario(
        scenario_id="s1",
        network_id="n1",
        demand_id="d1",
        interventions=draft.interventions,
        mechanisms=draft.mechanisms,
        sumocfg=draft.sumocfg,
        content_hash="c1",
        traci_script=draft.script,
    )
    assert scenario.is_online


def test_dynamic_demand_scale_is_named_as_unsupported_not_sent_round_in_circles() -> None:
    """§2.5 has no cell for it: no mechanism satisfies it, so the message must say so
    rather than pointing the agent at the mechanism the other check will reject."""
    dynamic_scale = Intervention(
        type=InterventionType.DEMAND_SCALE,
        target=None,
        condition=Condition(metric=Metric.OCCUPANCY, target="E12", op=Operator.GT, value=0.8),
    )
    for mechanism in (RegenerateDemandMechanism(demand_id="d2"), ScriptMechanism()):
        with pytest.raises(ValueError, match="not supported in v1"):
            scenario_draft(interventions=(dynamic_scale,), mechanisms=(mechanism,))


def test_a_note_task_follows_the_final_answer() -> None:
    abstain = ExpertAnswer(
        answer="need a run",
        basis=Basis.EXTRAPOLATED,
        confidence=0.2,
        needs_simulation=True,
        proposed_experiment=Question(text="close E12", intent=Intent.RUN),
    )
    with pytest.raises(ValueError, match="final round"):
        NoteTask(round=ExpertRound(question="q", answer=abstain))


def test_a_scenario_appears_once_in_the_allow_list() -> None:
    entry = NoteScenario("s1", "base", ExperimentRole.BASELINE, "as it is", simulated=True)
    with pytest.raises(ValueError, match="twice"):
        NoteTask(round=ExpertRound(question="q", answer=expert_answer()), scenarios=(entry, entry))
