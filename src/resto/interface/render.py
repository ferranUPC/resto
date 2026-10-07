"""Rendering of studies as Markdown or plain text, by code.

`failed` and `awaiting_user` studies are rendered here without any model call (ADR-0025 §3,
E5.11): the Executor already knows what went wrong, so the Output Composer only runs for `completed`
studies. A failed study is shown in three blocks — what happened, what was done (a rerun of the same
request reuses it), what the user can do (by `StepError.kind`); an `awaiting_user` study lists the
Input Parser's ambiguities, or what a specialist needs from the user. A `completed` study renders
its `Report` (E5.4): the model's prose as written, every table and line of fixed shape by code.

`render_study_text` renders the same data for a plain terminal: no Markdown syntax in the fixed
layout, ids cut to 8 characters, columns aligned with spaces.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

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
        lines += ["", f"## {_section_title(section.title)}", "", _prose(section.body)]
    lines += ["", "## Claims", ""]
    lines += [_claim(c) for c in report.claims] or ["No claims."]
    lines += ["", "## Evidence", "", "| Ref | Kind | Description |", "| --- | --- | --- |"]
    for ref, kind, description in _evidence_rows(study):
        lines.append(f"| `{_cell(ref)}` | {kind} | {_cell(description) if description else '-'} |")
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


def _section_title(title: str, *, upper: bool = False) -> str:
    """A model section title on one line, marked if it reads as a fixed heading."""
    clean = _line(title).lstrip("#").strip()
    if not clean:
        return "UNTITLED SECTION" if upper else "Untitled section"
    marked = clean.casefold() in _FIXED_HEADINGS
    shown = clean.upper() if upper else clean
    return f"{shown} (from the Composer)" if marked else shown


def _evidence_rows(study: Study) -> list[tuple[str, str, str]]:
    """The evidence the report's claims cite, in order of first citation: ref, kind, excerpt
    (empty if none). A ref the Expert's answer does not hold has kind `unresolved`."""
    report = study.report
    assert report is not None  # Study invariant: completed <=> a report
    known = {e.ref: e for e in study.rounds[-1].answer.evidence}
    cited = dict.fromkeys(ref for c in report.claims for ref in c.evidence_refs)
    rows = []
    for ref in cited:
        ev = known.get(ref)
        rows.append(
            (ref, ev.kind.value if ev else "unresolved", ev.excerpt if ev and ev.excerpt else "")
        )
    return rows


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


def _done(
    k: int, phase: Phase, *, tick: str = "`", ids: Mapping[str, str] | None = None
) -> list[str]:
    """What a phase did, as "- " bullets. `tick` quotes tool and arm names; `ids` shortens
    scenario ids."""
    ok = [s for s in phase.steps if s.status is StepStatus.OK]
    if not ok and not phase.experiments:
        return []
    lines = [f"{_phase_name(k).capitalize()}:"]
    for step in ok:
        produced = f": {', '.join(step.produced_ids)}" if step.produced_ids else ""
        lines.append(f"- {tick}{step.tool}{tick} ok{produced}")
    for e in phase.experiments:
        origin = "reused" if e.reused else "run now"
        lines.append(
            f"- experiment {tick}{e.arm}{tick} ({e.role}, {origin}): scenario "
            f"{(ids or {}).get(e.scenario_id, e.scenario_id)}, "
            f"{len(e.result_ids)} result(s)"
        )
    if phase.round is not None:
        outcome = "asked for a simulation" if phase.round.answer.needs_simulation else "answered"
        lines.append(f"- the Expert {outcome}")
    return lines


# --- plain text ---

_TEXT_ID_LENGTH = 8


def render_study_text(study: Study) -> str:
    """A `completed`, `failed` or `awaiting_user` study as plain text, with the content of
    `render_study` and none of its Markdown syntax (no `#`, pipes or backticks in the fixed layout).

    The model's prose is inserted as written, and the fields shown on one line are one line.
    Study and scenario ids are cut to 8 characters, longer only for two that would collide.

    Raises:
        ValueError: the study is still planning or running: it has nothing to show yet.
    """
    if study.status not in (StudyStatus.COMPLETED, StudyStatus.FAILED, StudyStatus.AWAITING_USER):
        raise ValueError(
            f"a study is rendered once completed, failed or awaiting_user, not {study.status}"
        )
    ids = _short_ids(
        [study.study_id, *(e.scenario_id for p in study.phases for e in p.experiments)]
    )
    lines = [
        f"STUDY {ids[study.study_id]}  ({study.status})",
        f"Question: {_line(study.question.text)}",
        "",
    ]
    if study.status is StudyStatus.COMPLETED:
        lines += _text_completed(study, ids)
    elif study.status is StudyStatus.FAILED:
        lines += _text_failed(study, ids)
    else:
        lines += _text_awaiting_user(study, ids)
    return "\n".join(lines) + "\n"


def _short_ids(ids: list[str]) -> dict[str, str]:
    """Each id cut to 8 characters, or to the shortest prefix no other id shares."""
    distinct = list(dict.fromkeys(ids))
    out = {}
    for i in distinct:
        n = _TEXT_ID_LENGTH
        while n < len(i) and any(o != i and o.startswith(i[:n]) for o in distinct):
            n += 1
        out[i] = i[:n]
    return out


def _columns(rows: Sequence[tuple[str, ...]]) -> list[str]:
    """`rows` indented and aligned in columns separated by two spaces."""
    if not rows:
        return ["  None."]
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return [
        "  " + "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)).rstrip()
        for row in rows
    ]


def _text_completed(study: Study, ids: Mapping[str, str]) -> list[str]:
    report = study.report
    assert report is not None  # Study invariant: completed <=> a report
    lines = ["SUMMARY", report.summary]
    for section in report.sections:
        lines += ["", _section_title(section.title, upper=True), section.body]
    lines += ["", "CLAIMS"]
    lines += [_text_claim(c) for c in report.claims] or ["  No claims."]
    lines += ["", "EVIDENCE"]
    lines += _columns([(ref, kind, _line(d) or "-") for ref, kind, d in _evidence_rows(study)])
    lines += ["", "EXPERIMENTS"]
    rows = []
    for k, phase in enumerate(study.phases):
        for e in phase.experiments:
            n = len(e.result_ids)
            rows.append(
                (
                    f"phase {k}",
                    _line(e.arm),
                    _line(str(e.role)),
                    f"scenario {ids[e.scenario_id]}",
                    f"{n} result" + ("" if n == 1 else "s"),
                    "reused" if e.reused else "run now",
                )
            )
    lines += _columns(rows)
    lines += ["", "MODE AND BASIS", f"  {report.mode}, {report.basis}", "", "LIMITATIONS"]
    lines += [f"  - {_line(x)}" for x in report.limitations] or ["  None stated."]
    return lines


def _text_claim(claim: Claim) -> str:
    value = f" [value: {_line(claim.value)}]" if claim.value else ""
    refs = ", ".join(_line(r) for r in claim.evidence_refs)
    return f"  - {_line(claim.text)}{value} [evidence: {refs}]"


def _text_done(study: Study, ids: Mapping[str, str]) -> list[str]:
    return [
        f"  {line}" if line.startswith("- ") else line
        for i, phase in enumerate(study.phases)
        for line in _done(i, phase, tick="", ids=ids)
    ]


def _text_failed(study: Study, ids: Mapping[str, str]) -> list[str]:
    k = len(study.phases) - 1
    step = study.phases[-1].failed_step
    assert step is not None and step.error is not None  # Study invariant: failed <=> a failed step
    error = step.error
    lines = [
        "WHAT HAPPENED",
        f"Step {step.tool} of {_phase_name(k)} failed ({error.kind}): {error.message}",
    ]
    lines += [f"  - {d}" for d in error.details if d]
    lines += ["", "WHAT WAS DONE"]
    done = _text_done(study, ids)
    if done:
        lines += [*done, "", "A rerun of the same request reuses everything listed here."]
    else:
        lines.append("Nothing was run or stored before the failure.")
    lines += ["", "WHAT YOU CAN DO", WHAT_TO_DO[error.kind]]
    return lines


def _text_awaiting_user(study: Study, ids: Mapping[str, str]) -> list[str]:
    needs = study.phases[-1].needs_user
    if needs is None:
        assert study.question.is_ambiguous  # Study invariant: awaiting_user needs one of the two
        return [
            "WHAT HAPPENED",
            "The question is ambiguous:",
            *(f"  - {_line(a)}" for a in study.question.ambiguities),
            "",
            "WHAT WAS DONE",
            "Nothing was run: the study stopped before planning.",
            "",
            "WHAT YOU CAN DO",
            "Ask again, saying precisely what you mean for each point above.",
        ]
    lines = ["WHAT HAPPENED", needs.message]
    if needs.candidates:
        lines += ["", "Candidates:", *(f"  - {c}" for c in needs.candidates)]
    if needs.found:
        lines += ["", "Already found:", *(f"  - {f.what} {f.id}" for f in needs.found)]
    lines += ["", "WHAT WAS DONE"]
    done = _text_done(study, ids)
    if done:
        lines += [*done, "", "A rerun of the same request reuses everything listed here."]
    else:
        stopped = _phase_name(len(study.phases) - 1)
        lines.append(f"Nothing was run or stored before {stopped} stopped.")
    lines += ["", "WHAT YOU CAN DO", *(f"  - {r}" for r in needs.recommendations)]
    return lines
