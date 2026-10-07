"""Rendering of studies as Markdown, by code.

`failed` and `awaiting_user` studies are rendered here without any model call (ADR-0025 §3,
E5.11): the Executor already knows what went wrong, so the Output Composer only runs for `completed`
studies. A failed study is shown in three blocks — what happened, what was done (a rerun of the same
request reuses it), what the user can do (by `StepError.kind`); an `awaiting_user` study lists the
Input Parser's ambiguities, or what a specialist needs from the user. A `completed` study renders
its `Report` (E5.4): the model's prose as written, every table and line of fixed shape by code.
"""

from __future__ import annotations

import re

from resto.domain.entities.study import Phase, Study, StudyStatus
from resto.domain.value_objects.report import Claim
from resto.domain.value_objects.step_record import StepErrorKind, StepStatus

WHAT_TO_DO: dict[StepErrorKind, str] = {
    StepErrorKind.USER_INPUT: (
        "Rephrase the question: the item named above does not exist on the network or cannot be "
        "simulated as asked."
    ),
    StepErrorKind.BUDGET: "Narrow the question, or rerun it with an explicitly raised budget.",
    StepErrorKind.AGENT: (
        "Retry the request, or change the approach (for example, say differently what to simulate)."
    ),
    StepErrorKind.PLANNING: (
        "The question cannot be planned as stated (see the cause above): rephrase it, for example "
        "naming the network or the change to simulate."
    ),
    StepErrorKind.INFRASTRUCTURE: (
        "Nothing to change on your side: the environment failed (see the logs named above). "
        "Retry once it is available again."
    ),
}
"""ADR-0025 §3: what the user can do, by failure kind."""


def render_study(study: Study) -> str:
    """A `completed`, `failed` or `awaiting_user` study as Markdown.

    Raises:
        ValueError: the study is still planning or running: it has nothing to show yet.
    """
    if study.status is StudyStatus.COMPLETED:
        return render_completed(study)
    if study.status is StudyStatus.FAILED:
        return render_failed(study)
    if study.status is StudyStatus.AWAITING_USER:
        return render_awaiting_user(study)
    raise ValueError(
        f"a study is rendered once completed, failed or awaiting_user, not {study.status}"
    )


def render_completed(study: Study) -> str:
    """A `completed` study's `Report` as Markdown: the fixed layout is code, the model's prose is
    inserted as written except for what would break that layout.

    The summary and section bodies keep their text, but a Markdown heading in them is demoted
    below the fixed ones (`####` or deeper; code fences are left alone). Section titles, claim
    text and values and table cells are single lines (newlines become spaces, `|` is escaped in
    cells), and a section titled like a fixed heading is marked as the Composer's.

    Raises:
        ValueError: the study is not completed.
    """
    if study.status is not StudyStatus.COMPLETED:
        raise ValueError("not a completed study")
    report = study.report
    assert report is not None  # Study invariant: completed <=> a report
    lines = [
        f"# Study {study.study_id}: report",
        "",
        f"> {_line(study.question.text)}",
        "",
        "## Summary",
        "",
        _prose(report.summary),
    ]
    for section in report.sections:
        lines += ["", f"### {_section_title(section.title)}", "", _prose(section.body)]
    lines += ["", "## Claims", ""]
    lines += [_claim(c) for c in report.claims] or ["No claims."]
    lines += ["", "## Evidence", "", "| Ref | Kind | Description |", "| --- | --- | --- |"]
    last_round = study.rounds[-1]
    known = {e.ref: e for e in last_round.answer.evidence}
    cited = dict.fromkeys(ref for c in report.claims for ref in c.evidence_refs)
    for ref in cited:
        ev = known.get(ref)
        kind = ev.kind.value if ev else "unresolved"
        text = _cell(ev.excerpt) if ev and ev.excerpt else "-"
        lines.append(f"| `{_cell(ref)}` | {kind} | {text} |")
    lines += [
        "",
        "## Experiments",
        "",
        "| Phase | Arm | Role | Scenario | Results | Origin |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for k, phase in enumerate(study.phases):
        for e in phase.experiments:
            origin = "reused" if e.reused else "run now"
            lines.append(
                f"| {k} | {_cell(e.arm)} | {_cell(str(e.role))} | {_cell(e.scenario_id)} "
                f"| {len(e.result_ids)} | {origin} |"
            )
    lines += [
        "",
        "## Mode and basis",
        "",
        f"Mode: {report.mode}. Basis: {report.basis}.",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {_line(x)}" for x in report.limitations] or ["None stated."]
    return "\n".join(lines) + "\n"


_FIXED_HEADINGS = frozenset(
    h.casefold()
    for h in ("Summary", "Claims", "Evidence", "Experiments", "Mode and basis", "Limitations")
)
_HEADING = re.compile(r"^(\s{0,3})(#{1,6})(?=\s|$)")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def _line(text: str) -> str:
    """`text` on one line."""
    return " ".join(text.split())


def _cell(text: str) -> str:
    """`text` as the content of one table cell."""
    return _line(text).replace("|", "\\|")


def _section_title(title: str) -> str:
    clean = _line(title).lstrip("#").strip()
    if not clean:
        return "Untitled section"
    if clean.casefold() in _FIXED_HEADINGS:
        return f"{clean} (from the Composer)"
    return clean


def _claim(claim: Claim) -> str:
    refs = ", ".join(f"`{_cell(r)}`" for r in claim.evidence_refs)
    value = f"value: {_cell(claim.value)}; " if claim.value else ""
    return f"- {_cell(claim.text)} ({value}evidence: {refs})"


def _prose(text: str) -> str:
    """The model's text with its Markdown headings demoted to level 4 or deeper."""
    out: list[str] = []
    fenced = False
    for raw in text.splitlines():
        if _FENCE.match(raw):
            fenced = not fenced
        match = None if fenced else _HEADING.match(raw)
        if match:
            level = min(6, len(match.group(2)) + 3)
            raw = f"{match.group(1)}{'#' * level}{raw[match.end() :]}"
        out.append(raw)
    return "\n".join(out)


def render_failed(study: Study) -> str:
    if study.status is not StudyStatus.FAILED:
        raise ValueError("not a failed study")
    k = len(study.phases) - 1
    step = study.phases[-1].failed_step
    assert step is not None and step.error is not None  # Study invariant: failed <=> a failed step
    error = step.error
    lines = [
        f"# Study {study.study_id}: failed",
        "",
        f"> {study.question.text}",
        "",
        "## What happened",
        "",
        f"Step `{step.tool}` of {_phase_name(k)} failed ({error.kind}): {error.message}",
    ]
    lines += [f"- {d}" for d in error.details if d]
    lines += ["", "## What was done", ""]
    done = [line for i, phase in enumerate(study.phases) for line in _done(i, phase)]
    if done:
        lines += done
        lines += ["", "A rerun of the same request reuses everything listed here."]
    else:
        lines.append("Nothing was run or stored before the failure.")
    lines += ["", "## What you can do", "", WHAT_TO_DO[error.kind]]
    return "\n".join(lines) + "\n"


def render_awaiting_user(study: Study) -> str:
    if study.status is not StudyStatus.AWAITING_USER:
        raise ValueError("not a study awaiting the user")
    question = study.question
    lines = [f"# Study {study.study_id}: awaiting your answer", "", f"> {question.text}", ""]
    needs = study.phases[-1].needs_user
    if needs is not None:
        lines += ["## What happened", "", needs.message]
        if needs.candidates:
            lines += ["", "Candidates:"]
            lines += [f"- {c}" for c in needs.candidates]
        if needs.found:
            lines += ["", "Already found:"]
            lines += [f"- {f.what} `{f.id}`" for f in needs.found]
        done = [line for i, phase in enumerate(study.phases) for line in _done(i, phase)]
        lines += ["", "## What was done", ""]
        if done:
            lines += done
            lines += ["", "A rerun of the same request reuses everything listed here."]
        else:
            stopped = _phase_name(len(study.phases) - 1)
            lines.append(f"Nothing was run or stored before {stopped} stopped.")
        lines += ["", "## What you can do", ""]
        lines += [f"- {r}" for r in needs.recommendations]
        return "\n".join(lines) + "\n"
    assert question.is_ambiguous  # Study invariant: awaiting_user needs ambiguities or a message
    lines += ["## What happened", "", "The question is ambiguous:"]
    lines += [f"- {a}" for a in question.ambiguities]
    what_to_do = "Ask again, saying precisely what you mean for each point above."
    lines += ["", "## What was done", "", "Nothing was run: the study stopped before planning."]
    lines += ["", "## What you can do", "", what_to_do]
    return "\n".join(lines) + "\n"


def _phase_name(k: int) -> str:
    if k == 0:
        return "phase 0 (the question as asked)"
    return f"phase {k} (the experiment proposed in round {k})"


def _done(k: int, phase: Phase) -> list[str]:
    ok = [s for s in phase.steps if s.status is StepStatus.OK]
    if not ok and not phase.experiments:
        return []
    lines = [f"{_phase_name(k).capitalize()}:"]
    for step in ok:
        produced = f": {', '.join(step.produced_ids)}" if step.produced_ids else ""
        lines.append(f"- `{step.tool}` ok{produced}")
    for e in phase.experiments:
        origin = "reused" if e.reused else "run now"
        lines.append(
            f"- experiment `{e.arm}` ({e.role}, {origin}): scenario {e.scenario_id}, "
            f"{len(e.result_ids)} result(s)"
        )
    if phase.round is not None:
        outcome = "asked for a simulation" if phase.round.answer.needs_simulation else "answered"
        lines.append(f"- the Expert {outcome}")
    return lines
