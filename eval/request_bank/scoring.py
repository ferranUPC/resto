"""Input Parser scoring on the request bank (E3.4 → E5.1; `docs/evaluating-resto.md` §5).

- The effective form is compared (`effective_arms` / `effective_contrasts`): the flat shorthand and
  a single arm score the same; using the shorthand is reported, not graded.
- Arms are matched by content, never by label. An intervention is compared on `type`, `target`,
  `window` / `condition` and `params`, numbers within 1 % relative (`custom`: type, target and
  window); a window is compared exactly. `AddEdge.edge_id` becomes a placeholder named after the
  edge's junctions in both the change and the interventions targeting it, so only consistency is
  checked; an id no intervention targets is dropped.
- §4.1's `interventions` / `topology_changes` match is on the union of distinct items across all
  effective arms; `metrics_of_interest` is an exact set match on the `Measure` names.
- Arm structure (gating E5.1 at ≥ 90 % on multi-arm requests): the arms match as a set and the
  contrasts match as unordered pairs of arms.

A prediction that is `None` failed schema validation (after the Parser's retry); it scores False on
every graded field.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Any, TypeVar

from eval.request_bank.bank import BankRequest
from eval.request_bank.concepts import AmbiguousGold, Gold
from resto.domain.services.experiment_design import required_arms
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import AddEdge, TopologyModification

T = TypeVar("T")

REL_TOL = 0.01

THRESHOLDS = {
    "schema_validity": 0.98,
    "intent": 0.85,
    "interventions": 0.85,
    "topology_changes": 0.85,
    "metrics_of_interest": 0.85,
    "ambiguity_detection": 0.80,
    "arm_structure": 0.90,
}
"""E5.1 Done: §4.1 of the architecture doc, plus arm structure (evaluating-resto.md §5)."""

INTENT_AGREEMENT_THRESHOLD = 0.95


# --- comparison with tolerance -------------------------------------------------------------------


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _same(a: Any, b: Any) -> bool:
    """Structural equality; numbers within `REL_TOL`, a `TimeWindow` exactly."""
    if isinstance(a, TimeWindow) or isinstance(b, TimeWindow):
        return a == b
    if is_dataclass(a) and not isinstance(a, type):
        return type(a) is type(b) and all(
            _same(getattr(a, f.name), getattr(b, f.name)) for f in fields(a)
        )
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    x, y = _number(a), _number(b)
    if x is not None and y is not None:
        return math.isclose(x, y, rel_tol=REL_TOL, abs_tol=1e-9)
    return bool(a == b)


def _same_intervention(a: Intervention, b: Intervention) -> bool:
    if a.type is not b.type or not _same(a.target, b.target) or a.window != b.window:
        return False
    if a.type is InterventionType.CUSTOM:
        return True
    return _same(a.condition, b.condition) and _same(dict(a.params), dict(b.params))


def _distinct(items: Iterable[T], same: Callable[[T, T], bool]) -> list[T]:
    kept: list[T] = []
    for item in items:
        if not any(same(item, k) for k in kept):
            kept.append(item)
    return kept


def _bijection(
    gold: Sequence[T], pred: Sequence[T], same: Callable[[T, T], bool]
) -> list[int] | None:
    """For each gold item, the index of the predicted item it matches; None without a one-to-one
    match."""
    if len(gold) != len(pred):
        return None

    def extend(i: int, used: list[int]) -> list[int] | None:
        if i == len(gold):
            return used
        for j, candidate in enumerate(pred):
            if j not in used and same(gold[i], candidate):
                found = extend(i + 1, [*used, j])
                if found is not None:
                    return found
        return None

    return extend(0, [])


def _same_set(gold: Iterable[T], pred: Iterable[T], same: Callable[[T, T], bool]) -> bool:
    return _bijection(_distinct(gold, same), _distinct(pred, same), same) is not None


# --- canonical arms ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Arm:
    label: str
    changes: tuple[TopologyModification, ...]
    interventions: tuple[Intervention, ...]


def _rename(intervention: Intervention, names: Mapping[str, str]) -> Intervention:
    target = intervention.target
    if isinstance(target, EdgeTarget | LaneTarget) and target.edge_id in names:
        target = replace(target, edge_id=names[target.edge_id])
    condition = intervention.condition
    if condition is not None and condition.target in names:
        condition = replace(condition, target=names[condition.target])
    return replace(intervention, target=target, condition=condition)


def _targeted_ids(interventions: Iterable[Intervention]) -> set[str]:
    ids = set()
    for intervention in interventions:
        if isinstance(intervention.target, EdgeTarget | LaneTarget):
            ids.add(intervention.target.edge_id)
        if intervention.condition is not None:
            ids.add(intervention.condition.target)
    return ids


def _canonical_arms(question: Question) -> list[_Arm]:
    arms = []
    for arm in question.effective_arms:
        targeted = _targeted_ids(arm.interventions)
        names: dict[str, str] = {}
        changes: list[TopologyModification] = []
        for change in arm.topology_changes:
            if isinstance(change, AddEdge) and change.edge_id is not None:
                if change.edge_id in targeted:
                    names[change.edge_id] = f"<new {change.from_junction}->{change.to_junction}>"
                    change = replace(change, edge_id=names[change.edge_id])
                else:
                    change = replace(change, edge_id=None)
            changes.append(change)
        interventions = tuple(_rename(i, names) for i in arm.interventions)
        arms.append(_Arm(arm.label, tuple(changes), interventions))
    return arms


def _same_arm(a: _Arm, b: _Arm) -> bool:
    return _same_set(a.changes, b.changes, _same) and _same_set(
        a.interventions, b.interventions, _same_intervention
    )


def _arm_matching(gold: Question, pred: Question) -> dict[str, str] | None:
    """Predicted label → gold label (`base` → `base`), or None if the arms do not match as a set."""
    gold_arms, pred_arms = _canonical_arms(gold), _canonical_arms(pred)
    matched = _bijection(gold_arms, pred_arms, _same_arm)
    if matched is None:
        return None
    labels = {pred_arms[j].label: gold_arms[i].label for i, j in enumerate(matched)}
    return {BASE_ARM: BASE_ARM, **labels}


def _pairs(question: Question, rename: Mapping[str, str] | None = None) -> set[frozenset[str]]:
    to = rename or {}
    return {
        frozenset((to.get(c.treatment, c.treatment), to.get(c.reference, c.reference)))
        for c in question.effective_contrasts
    }


def arm_structure(gold: Question, pred: Question) -> bool:
    """The arms match as a set of contents and the contrasts as unordered pairs of those arms."""
    labels = _arm_matching(gold, pred)
    return labels is not None and _pairs(pred, labels) == _pairs(gold)


# --- per request ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RequestScore:
    """None means "not scored for this request"."""

    valid: bool
    intent: bool | None = None
    """Gold intent or one of the concept's accepted alternatives (graded)."""
    intent_strict: bool | None = None
    """Gold intent only (reported)."""
    ambiguity_detected: bool | None = None
    spurious_ambiguity: bool | None = None
    interventions: bool | None = None
    topology_changes: bool | None = None
    metrics_of_interest: bool | None = None
    arm_structure: bool | None = None
    multi_arm: bool = False
    required_arms: bool | None = None
    used_shorthand: bool | None = None
    network_ref: bool | None = None
    demand_ref: bool | None = None
    time_window: bool | None = None


def _union_interventions(question: Question) -> list[Intervention]:
    return [i for arm in _canonical_arms(question) for i in arm.interventions]


def _union_changes(question: Question) -> list[TopologyModification]:
    return [c for arm in _canonical_arms(question) for c in arm.changes]


def _same_ref(a: str | None, b: str | None) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def score_request(
    gold: Gold, pred: Question | None, also: frozenset[Intent] = frozenset()
) -> RequestScore:
    """`also`: intents accepted besides the gold one, where people read the request both ways
    (`concepts.ALSO_ACCEPTED`); `intent` counts them, `intent_strict` does not."""
    if isinstance(gold, AmbiguousGold):
        if pred is None:
            missed = False if gold.intent is not None else None
            return RequestScore(
                valid=False, intent=missed, intent_strict=missed, ambiguity_detected=False,
            )
        if gold.intent is None:
            return RequestScore(valid=True, ambiguity_detected=pred.is_ambiguous)
        return RequestScore(
            valid=True,
            intent=pred.intent is gold.intent or pred.intent in also,
            intent_strict=pred.intent is gold.intent,
            ambiguity_detected=pred.is_ambiguous,
        )

    multi_arm = len(gold.effective_arms) > 1
    if pred is None:
        return RequestScore(
            valid=False, intent=False, intent_strict=False, interventions=False,
            topology_changes=False,
            metrics_of_interest=False, arm_structure=False, multi_arm=multi_arm,
            required_arms=False,
        )
    labels = _arm_matching(gold, pred)
    required = (
        labels is not None
        and {labels[label] for label in required_arms(pred)} == set(required_arms(gold))
    )
    return RequestScore(
        valid=True,
        intent=pred.intent is gold.intent or pred.intent in also,
        intent_strict=pred.intent is gold.intent,
        spurious_ambiguity=pred.is_ambiguous,
        interventions=_same_set(
            _union_interventions(gold), _union_interventions(pred), _same_intervention
        ),
        topology_changes=_same_set(_union_changes(gold), _union_changes(pred), _same),
        metrics_of_interest=set(pred.metrics_of_interest) == set(gold.metrics_of_interest),
        arm_structure=labels is not None and _pairs(pred, labels) == _pairs(gold),
        multi_arm=multi_arm,
        required_arms=required,
        used_shorthand=not pred.arms if len(gold.effective_arms) == 1 else None,
        network_ref=_same_ref(gold.network_ref, pred.network_ref),
        demand_ref=_same_ref(gold.demand_ref, pred.demand_ref),
        time_window=gold.time_window == pred.time_window,
    )


# --- aggregation ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rate:
    hits: int
    total: int

    @property
    def value(self) -> float | None:
        return self.hits / self.total if self.total else None


def _rate(values: Iterable[bool | None]) -> Rate:
    scored = [v for v in values if v is not None]
    return Rate(sum(scored), len(scored))


def summarize(scores: Sequence[RequestScore]) -> dict[str, Rate]:
    """Graded metrics first (the keys of `THRESHOLDS`), then the reported ones."""
    return {
        "schema_validity": _rate(s.valid for s in scores),
        "intent": _rate(s.intent for s in scores),
        "interventions": _rate(s.interventions for s in scores),
        "topology_changes": _rate(s.topology_changes for s in scores),
        "metrics_of_interest": _rate(s.metrics_of_interest for s in scores),
        "ambiguity_detection": _rate(s.ambiguity_detected for s in scores),
        "arm_structure": _rate(s.arm_structure for s in scores if s.multi_arm),
        "intent_strict": _rate(s.intent_strict for s in scores),
        "arm_structure_single": _rate(s.arm_structure for s in scores if not s.multi_arm),
        "required_arms": _rate(s.required_arms for s in scores if s.multi_arm),
        "spurious_ambiguity": _rate(s.spurious_ambiguity for s in scores),
        "used_shorthand": _rate(s.used_shorthand for s in scores),
        "network_ref": _rate(s.network_ref for s in scores),
        "demand_ref": _rate(s.demand_ref for s in scores),
        "time_window": _rate(s.time_window for s in scores),
    }


def done(summary: Mapping[str, Rate]) -> dict[str, bool]:
    """Each E5.1 threshold met? A metric with nothing to score is not met."""
    return {
        name: (rate := summary[name]).value is not None and rate.value >= threshold
        for name, threshold in THRESHOLDS.items()
    }


AXES: dict[str, Callable[[BankRequest], str]] = {
    "category": lambda r: str(r.category),
    "split": lambda r: r.split,
    "lang": lambda r: r.lang,
    "style": lambda r: str(r.style or "plain"),
    "vague": lambda r: str(r.vague or "none"),
    "noise": lambda r: str(r.noise or "none"),
}


def breakdown(
    requests: Sequence[BankRequest], scores: Mapping[str, RequestScore], axis: str
) -> dict[str, dict[str, Rate]]:
    """`summarize` per value of one axis (`AXES`), over the requests that have a score."""
    groups: dict[str, list[RequestScore]] = defaultdict(list)
    for request in requests:
        if request.id in scores:
            groups[AXES[axis](request)].append(scores[request.id])
    return {value: summarize(group) for value, group in sorted(groups.items())}


def _same_reading(a: Question | None, b: Question | None) -> bool:
    if a is None or b is None:
        return a is b
    return (
        a.intent is b.intent
        and a.is_ambiguous == b.is_ambiguous
        and set(a.metrics_of_interest) == set(b.metrics_of_interest)
        and arm_structure(a, b)
    )


def consistency(
    requests: Sequence[BankRequest], predictions: Mapping[str, Question | None]
) -> Rate:
    """Share of concepts whose requests sharing one gold (base + non-vaguised variants) were all
    read the same way — intent, ambiguity flag, metrics and arm structure — right or wrong."""
    by_concept: dict[str, list[Question | None]] = defaultdict(list)
    for request in requests:
        if request.vague is None and request.id in predictions:
            by_concept[request.concept_id].append(predictions[request.id])
    groups = [g for g in by_concept.values() if len(g) > 1]
    return Rate(sum(all(_same_reading(g[0], p) for p in g[1:]) for g in groups), len(groups))


def intent_agreement(runs: Sequence[Mapping[str, Question | None]]) -> Rate:
    """Share of requests on which every repeated run gives the same `intent` (§4.1: ≥ 95 % over 3
    runs); a failed run counts as a disagreement."""
    ids = set.intersection(*(set(run) for run in runs)) if runs else set()
    agreed = 0
    for request_id in ids:
        preds = [run[request_id] for run in runs]
        intents = {p.intent for p in preds if p is not None}
        agreed += None not in preds and len(intents) == 1
    return Rate(agreed, len(ids))
