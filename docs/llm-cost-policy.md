# LLM provider and cost policy

Read before a real OpenRouter call or any evaluation run. This file is the single source for the policy;
`CLAUDE.md` only points here.

## Provider

The real `ToolAgent` calls models through OpenRouter (`https://openrouter.ai/api/v1`), not the
Anthropic API directly. The architecture doc's module name (`adapters/llm/anthropic_client.py`) predates
this choice; the file may end up talking to OpenRouter's OpenAI-compatible endpoint under that name, or get
renamed when the module is actually built. Config lives in `.env` (gitignored; copy `.env.example` and fill
in `OPENROUTER_API_KEY`).

## Policy

Cost is a hard constraint on this project, not a preference:

- **One default model, no exceptions by default.** Every agent run (`ToolAgent.run`) uses
  `RESTO_LLM_DEFAULT_MODEL` (`deepseek/deepseek-v4.1-flash`, DeepSeek's cheap/fast tier via OpenRouter).
  Nothing in the codebase should silently switch to a pricier model.
- **Evaluation tooling exceptions (approved 2026-09-23, never for agent runs).** The request-bank variant
  pipeline (`eval/request_bank/`) uses `RESTO_BANK_GENERATOR_MODEL` (`qwen/qwen3.5-9b`) and
  `RESTO_BANK_VERIFIER_MODEL` (`meta-llama/llama-3.3-70b-instruct`); Parser comparison runs may name
  `mistralai/ministral-3b-2512` or `google/gemma-3-12b-it` explicitly per run. All are cheaper than the
  default; see `eval/decisions-log.md`.
- **No escalation model is approved right now** (`RESTO_LLM_ESCALATION_MODEL` is blank on purpose). If a
  task genuinely cannot be done on the light model, stop and ask the user which stronger model to use and
  confirm the expected cost before spending. Never fall back to a paid alternative on your own judgment.
- **Development runs go now; measurement runs wait for a validation pass** (2026-09-24, replaces the
  earlier "> $1 waits" rule. The line is the run's purpose, not its price). The maintainer pays out of
  pocket until funding is settled, and a measurement paid early is paid again whenever requirements change.
  - A **development run** lets work move forward: a smoke test, a tuning iteration, a 1-repetition sweep
    to see whether a module is on track. It runs directly, with its cost stated up front. If a single
    development run is estimated above $1, stop and ask first. Each task's tuning log keeps the running
    total spent.
  - A **measurement run** produces the figure a DoD threshold reads and is not needed to keep building.
    It does **not** run now, whatever its price, even with the user's go-ahead on the surrounding task.
    It waits for one of the two validation passes dated in the work plan: **Validation 1** (mid-December:
    reduced checkpoints on dev splits only; definitive size for frozen modules only if funding is
    confirmed by then) or **Validation 2** (before the results chapter, E8.5: every definitive
    measurement, each suite once; a failure there is reported as a result, not re-tuned). Held-out
    splits are only ever used inside a validation pass.
  - The unit is the **measurement suite**. Splitting one into cheaper runs to get under a limit is not
    allowed. Suites and their costs are listed in `eval/measurement-plans.md`. Both passes together are
    capped at **$30** unless funding arrives; under the cap a suite shrinks in scale (inputs × repetitions
    × models), it is not dropped.
- **Tests never call the real API.** Every agent module is tested against the shared fake `ToolAgent`
  (ADR-0001). `pytest` must not require `OPENROUTER_API_KEY` or produce network calls to OpenRouter.
- **Keep `Budget` caps conservative** (`RESTO_LLM_MAX_OUTPUT_TOKENS`, `RESTO_LLM_MAX_STEPS`). Raise them
  deliberately for the one call that needs it; don't bump the defaults to make a symptom go away.
- Prefer a dry run / the fake agent over a real call whenever what's being checked is code behavior rather
  than actual model output.
