"""What an agent returns: data plus references to the artifacts it produced, plus a rationale.

Promotion (validation, identity, persistence) is code — see architecture §2.2. That is why no
draft here carries an id, a content hash, a `status` or a `provenance`: those fields are the
promotion step's to write, and leaving them off the draft makes it impossible for an agent to
forge one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.calibration_round import CalibrationRound
from resto.domain.value_objects.demand_source import DemandSource
from resto.domain.value_objects.demand_spec import DemandSpec
from resto.domain.value_objects.expert_answer import Basis, Evidence
from resto.domain.value_objects.fidelity import Fidelity
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.mechanism import (
    Mechanism,
    check_mechanisms_match,
    needs_script,
)
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.probe_report import ProbeReport
from resto.domain.value_objects.sanity_report import DEFAULT_MIN_SCC_RATIO, SanityReport
from resto.domain.value_objects.traci_script import TraciScript

ElementKind = Literal["edge", "junction", "connection", "tls"]


@dataclass(frozen=True, slots=True)
class UnresolvedIssue:
    """A defect the Network Author found but had no tool to fix (architecture §2.4).

    Doubles as the tool backlog: `needed_tool` is what the v1 catalogue was missing.
    """

    element_kind: ElementKind
    element_id: str
    issue: str
    needed_tool: str | None = None

    def __post_init__(self) -> None:
        if not self.element_id:
            raise ValueError("an UnresolvedIssue must name the affected element")
        if not self.issue.strip():
            raise ValueError("an UnresolvedIssue must describe the defect")


@dataclass(frozen=True, slots=True)
class RejectedIntervention:
    """An intervention the Scenario Builder could not implement, with the reason why.

    DoD §4.5 forbids silent coercion: an unimplementable spec is reported, never approximated.
    """

    intervention: Intervention
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a rejected intervention must carry a reason")


@dataclass(frozen=True, slots=True)
class NetworkDraft:
    """Network Author output. The recipe is what makes the network replayable without an LLM."""

    recipe: NetworkRecipe
    net_artifact: ArtifactRef
    sanity_report: SanityReport
    rationale: str
    probe_report: ProbeReport | None = None
    unresolved: tuple[UnresolvedIssue, ...] = ()

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("a NetworkDraft must explain what the agent decided")
        if not self.net_artifact.path.name.endswith(".net.xml"):
            raise ValueError("net_artifact must point to a .net.xml file")

    def is_silent_failure(self, min_scc_ratio: float = DEFAULT_MIN_SCC_RATIO) -> bool:
        """Sanity failed and the agent reported nothing — the "good enough" exit DoD §4.3 bans.

        Threshold-dependent, so promotion checks it with the NetworkTask's own threshold.
        """
        return not self.sanity_report.passes(min_scc_ratio) and not self.unresolved


@dataclass(frozen=True, slots=True)
class DemandDraft:
    """Demand Generator output: trips plus routes computed for one network."""

    spec: DemandSpec
    trips_artifact: ArtifactRef
    routes_artifact: ArtifactRef
    rationale: str
    sources: tuple[DemandSource, ...] = ()
    fidelity: Fidelity | None = None
    calibration_rounds: tuple[CalibrationRound, ...] = ()

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("a DemandDraft must explain what the agent decided")
        rounds = [r.round for r in self.calibration_rounds]
        if rounds != sorted(set(rounds)):
            raise ValueError("calibration rounds must be strictly increasing")
        if self.fidelity is not None and not self.calibration_rounds:
            raise ValueError("fidelity is measured by calibration runs; none were recorded")


@dataclass(frozen=True, slots=True)
class ScenarioDraft:
    """Scenario Builder output. `script` may still be failing lint or dry_run here: that is
    information the promotion step acts on, whereas a promoted Scenario requires it runnable."""

    interventions: tuple[Intervention, ...]
    mechanisms: tuple[Mechanism, ...]
    sumocfg: ArtifactRef
    rationale: str
    additional_files: tuple[ArtifactRef, ...] = ()
    script: TraciScript | None = None
    rejected: tuple[RejectedIntervention, ...] = ()

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("a ScenarioDraft must explain what the agent decided")
        check_mechanisms_match(self.interventions, self.mechanisms)
        if needs_script(self.mechanisms) and self.script is None:
            raise ValueError("script mechanisms require a traci_script")


@dataclass(frozen=True, slots=True)
class ExpertNoteDraft:
    """Network Expert output after an experiment: the prose only.

    `provenance`, `status`, `note_id` and the references to network/scenario/study are written
    by `write_note`, which knows the experiment the note came from.
    """

    text: str
    basis: Basis
    evidence: tuple[Evidence, ...] = ()
    context_tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("an ExpertNoteDraft requires text")
        if self.basis is Basis.OBSERVED and not self.evidence:
            raise ValueError("an observed note must point at what was observed")
