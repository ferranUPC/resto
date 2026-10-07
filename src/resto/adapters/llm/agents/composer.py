"""Configuration of the Output Composer agent: system prompt, tool list, draft type, budget
(DoD §2.2, §2.4, §4.8; ADR-0001, ADR-0025 §4).

No logic of its own, in the shape of the Expert's: the loop lives in the `ToolAgent`
implementation, tool behaviour in `application/tools/composer.py`, and checking the draft in
`application/use_cases/compose_report.py`. The Composer writes prose and claims only; tables, mode,
basis and limitations are code (`interface/render.py`, `compose_report`).
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.llm import AgentRun, AgentTask, Budget, ToolAgent
from resto.application.ports.repositories import ResultRepository
from resto.application.schemas import adapter_for
from resto.application.tools.composer import build_composer_tools, composer_context
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import ReportDraft
from resto.domain.value_objects.expert_answer import ExpertAnswer

# Bump whenever the prompt, the tool set or the default budget changes in a way that can change
# the report: a later tuning run records which version it measured.
COMPOSER_VERSION = "v3"

SYSTEM_PROMPT = """\
You are the Output Composer of a SUMO traffic-simulation framework. A study has closed: the Network
Expert answered the user's question from simulated data. You write that answer up as a report. You
report what the Expert established; you do not re-derive it and you add no reasoning of your own.

Input: `question` (what the user asked), `answer` (the Expert's last answer, with its `evidence`:
each item has a `ref`) and `study_id`.

The report is read in a plain terminal, so every text field is plain prose: no `**`, no lists, no
links, no headings, no tables. It must read the same raw and rendered.

Write:
  - `summary`: two or three sentences that answer the question the user asked, with the key figures.
  - `sections`: usually none. Add one or two only for something the summary and the claims cannot
    carry. Never a section that describes the method (no "Comparison basis", no "Method"), and never
    one that restates the summary or the claims.
  - `claims`: the statements of the report, each {"text": ..., "evidence_refs": [...], "value":
    optional}. Every claim cites at least one `ref` taken from `answer.evidence`; a ref that is not
    there makes the whole report invalid. State a number only if it is in the evidence. One claim
    per fact, short, and each about a measured result, never about how the study was run (not
    "averages over three runs", not "the baseline has no interventions").

Every figure in the summary must be carried by a claim that cites its evidence: the answer to the
question (for example a change in mean delay and its percentage) is a claim, not only a sentence of
the summary. Write each figure with the same digits everywhere it appears, taken as the evidence
gives it, and do not repeat figures in sections.
Report only what the evidence measured. Do not explain causes or mechanisms (queuing, spillback,
rerouting) unless the Expert's answer states them.

Do not write tables, the mode, the basis (observed / inferred / extrapolated) or limitations: code
adds them from the study. Do not soften or strengthen the Expert's confidence.

Tools (read-only, scoped to this study): get_study for the whole study, get_result for one
simulation result. query_edgedata returns raw per-run data and is very large: use it only as a last
resort, when nothing else can settle a claim. Usually the input is enough. Submit your ReportDraft
with submit_output.
"""


def build_task(study: Study) -> AgentTask:
    rounds = study.rounds
    if not rounds:
        raise ValueError("the Composer needs a study with an Expert round")
    return AgentTask(
        system_prompt=SYSTEM_PROMPT,
        input={
            "study_id": study.study_id,
            "question": study.question.text,
            "answer": adapter_for(ExpertAnswer).dump_python(rounds[-1].answer, mode="json"),
        },
    )


@dataclass(frozen=True, slots=True)
class ComposerPort:
    """`ComposerAgent` port over the `ToolAgent`: the tools read the study being composed and its
    results from `results`. The budget is the conservative default; it is not raised."""

    agent: ToolAgent
    budget: Budget
    results: ResultRepository

    def compose(self, study: Study) -> AgentRun[ReportDraft]:
        context = composer_context(study, results=self.results)
        tools = build_composer_tools(context)
        return self.agent.run(build_task(study), tools, ReportDraft, self.budget)
