# Input Parser tuning log

- Status: living document, started 2026-09-23
- Purpose: record every change to the Input Parser agent (prompt, budget, output handling) with the
  reason behind it and its measured effect, so the thesis can explain how the Parser was tuned.
- Related: the request bank and its scoring rules are in [`evaluating-resto.md`](evaluating-resto.md) §5;
  thresholds in [`tfm-architecture-and-dod.md`](tfm-architecture-and-dod.md) §4.1, plus arm structure
  ≥ 90 % (evaluating-resto.md §5, 2026-09-23).

---

## 1. Method

- **Versions.** `PARSER_VERSION` in `src/resto/adapters/llm/agents/input_parser.py` names the agent
  configuration; every benchmark run stores it.
- **Tuning on dev only.** Versions are measured on the dev split of the request bank (45 concepts,
  212 requests) with `python -m eval.parser_benchmark.run --name <version>-dev --model <model>`.
  Held-out (20 concepts, 94 requests) is run once, with `--split held_out --final`, to measure E5.1
  Done; its requests are never read while tuning. Reports live in `eval/parser_benchmark/reports/`.
- **Bank fixes are not optimisations.** A variant that turns out not to say what its gold says is
  fixed in the bank (noted per variant in `variants.json`) and logged in §3, not counted as a
  Parser improvement.

## 2. Versions

All runs: `deepseek/deepseek-v4.1-flash`, 1 repetition, estimated cost at the conservative prices of
`adapters/llm/pricing.py`.

| Version | Change | Run | Result | Cost |
|---|---|---|---|---|
| v1 | First prompt: field rules, intervention vs topology, shorthand vs arms and contrasts, ambiguity rules, prompt-injection rule, three examples on a network outside the bank. 2 model calls (one retry), shared 2048 output tokens. | `smoke-v1`, 9 dev requests | 9/9 valid; R065 (7 arms) cut at 2048 tokens, leaving only `intent` | $0.010 |
| v2 | Parser output cap 4096 (`PARSER_MAX_OUTPUT_TOKENS`); the model writes `"."` as `text` and the port fills in the request. | `smoke-v2`, same 9 | every graded metric 100 % but intent (R026 read as `compare`) | $0.010 |
| v3 | Intent follows the form of the question, not the number of options ("what would happen if A, if B and if both" is counterfactual). | `v3-dev`, 212 | every threshold met: validity 99.5 %, intent 95.6 %, interventions 99.2 %, topology 100 %, metrics 99.2 %, ambiguity 92.0 %, arm structure 93.0 %; consistency 73.3 % | $0.226 |
| v4 | Five general rules from v3's failures: an imperative that sets up changes and asks for a result is `run` even if ambiguous; a bare list of changes is ambiguous even when a combined run looks likely; no contrasts without arms; a combination compared with one of its parts has that part as reference; "or something else" without alternatives is ambiguous. | `v4-dev`, 212 (bank fixes of §3 applied) | validity, intent, interventions, topology, metrics 100 %; ambiguity 98.9 %; arm structure 95.3 %; no spurious ambiguity; consistency 91.1 % | $0.227 |

Remaining v4 failures on dev (3): a German grouping-vague list still read as one combined run
(R020.de-vague_grouping), and R065 in German and Chinese (one extra arm; one contrast against `base`
instead of B). Not tuned further: these are the bank's hardest items, and more rules for single dev
requests would fit dev rather than improve the Parser.

## 3. Bank fixes found by Parser runs

The v3 dev run exposed variants that did not say what their gold says; they were fixed before v4
(the v3 numbers are on the old texts):

| Variant | Defect |
|---|---|
| R004.en-telegraphic | "together" lost: the Parser rightly asked whether the two changes go together |
| R026.en-telegraphic | "each" lost: read as one combined treatment |
| R009.en-messy | "backed up" names no measure (gold `waiting_time`) |
| R054.ca, R054.es | the translation of an unintelligible request was intelligible |

The same review read the 24 pilot variants in full (they had only had the pilot's sample review) and
fixed three typos (R003.de, R004.es, R005.ca).
