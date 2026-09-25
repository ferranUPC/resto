from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.arm import BASE_ARM, Arm, Contrast, contains
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import TopologyModification


class Intent(StrEnum):
    DESCRIBE = "describe"
    DIAGNOSE = "diagnose"
    COUNTERFACTUAL = "counterfactual"
    COMPARE = "compare"
    RUN = "run"


SHORTHAND_ARM = "treatment"
"""Label of the arm the flat `interventions` / `topology_changes` stand for."""


class Mode(StrEnum):
    FREE = "free"
    FORCED = "forced"


@dataclass(frozen=True, slots=True)
class Question:
    """What the user asked, as understood by the Input Parser. A plain doubt is
    `describe`/`diagnose`; a hypothesis is `counterfactual`/`compare`.

    What to simulate is said in one of two forms (ADR-0027): the flat `interventions` /
    `topology_changes` are the shorthand for one treatment against the base; `arms` + `contrasts`
    name several combinations and which pairs to compare. Code reads `effective_arms` and
    `effective_contrasts`, which cover both."""

    text: str
    intent: Intent
    mode: Mode = Mode.FREE
    network_ref: str | None = None
    demand_ref: str | None = None
    interventions: tuple[Intervention, ...] = ()
    topology_changes: tuple[TopologyModification, ...] = ()
    metrics_of_interest: tuple[str, ...] = ()
    time_window: TimeWindow | None = None
    context_tags: frozenset[str] = frozenset()
    ambiguities: tuple[str, ...] = ()
    arms: tuple[Arm, ...] = ()
    contrasts: tuple[Contrast, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a Question requires text")
        if self.arms and (self.interventions or self.topology_changes):
            raise ValueError("use arms or the flat interventions/topology_changes, not both")
        if self.contrasts and not self.arms:
            raise ValueError("contrasts compare named arms: give the arms")
        labels = [a.label for a in self.arms]
        if len(set(labels)) != len(labels):
            raise ValueError("arm labels must be unique")
        contents = [(a.topology_changes, a.interventions) for a in self.arms]
        # Pairwise, not a set: an Intervention's `params` mapping is not hashable.
        if any(c in contents[:i] for i, c in enumerate(contents)):
            raise ValueError("two arms describe the same combination")
        known = {*labels, BASE_ARM}
        for c in self.contrasts:
            if c.treatment not in known or c.reference not in known:
                raise ValueError(f"contrast {c.treatment} vs {c.reference} names an unknown arm")
        if len(set(self.contrasts)) != len(self.contrasts):
            raise ValueError("contrasts must not repeat")

    @property
    def is_ambiguous(self) -> bool:
        return bool(self.ambiguities)

    @property
    def effective_arms(self) -> tuple[Arm, ...]:
        """The listed arms, or the shorthand as one arm labelled `SHORTHAND_ARM`."""
        if self.arms or not (self.interventions or self.topology_changes):
            return self.arms
        return (Arm(SHORTHAND_ARM, self.topology_changes, self.interventions),)

    @property
    def effective_contrasts(self) -> tuple[Contrast, ...]:
        """The listed contrasts, or each arm against the base.

        Of two nested arms, the one contained in the other is the reference, however the contrast
        was written: the base is always a reference, and a combination is measured against its
        part (ADR-0027 §1). A contrast listed both ways counts once. Two arms that are not nested
        keep the order the question gives."""
        if not self.contrasts:
            return tuple(Contrast(a.label) for a in self.effective_arms)
        arms = {a.label: a for a in self.arms}
        oriented: list[Contrast] = []
        for c in self.contrasts:
            treatment, reference = arms.get(c.treatment), arms.get(c.reference)
            if contains(reference, treatment) and not contains(treatment, reference):
                c = Contrast(c.reference, c.treatment)
            if c not in oriented:
                oriented.append(c)
        return tuple(oriented)
