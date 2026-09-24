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
| v5 | Intent by meaning, not by the verb (evaluating-resto.md §5, 2026-09-24): `run` = the figures of a given setup with nothing to compare against; `counterfactual` = the effect of changes against today or another named setup ("try X and see", "with and without X"); `compare` = a choice between alternatives, with or without the word. The old "form of the question decides" rule removed. | `v5-dev`, 212 (gold of R035 now `counterfactual`) | every threshold met: validity, interventions, topology, metrics 100 %; intent 96.2 %; ambiguity 98.9 %; arm structure 97.7 %; no spurious ambiguity | $0.241 |
| v6 | Intent is what the user wants, never what it takes to answer: "run/simulate X and report Y" is `counterfactual`; `run` is kept for an action wanted as an end in itself ("add an edge from J7 to J9"), with no question about its effect; the prompt says whether to simulate is decided later. | `v6-dev`, 212 (the ten `run` concepts now `counterfactual`); +20 requests of the new `run` concepts R066/R067/R070/R071, all correct ($0.020) | every threshold met: validity, interventions, topology, metrics 100 %; intent 99.4 %; ambiguity 97.7 %; arm structure 95.3 %; no spurious ambiguity; consistency 88.9 % | $0.244 |

Remaining v6 failures on dev (5): R035.zh read as `compare` (its text says "compare the current
network with a version…", an effect with nothing to choose); R020.de-vague_grouping and R044.zh
read a bare list as one combined run; R065 and R065.zh, the seven-arm request. No rule added for
single requests. `run` is measured again through R066–R071 (evaluating-resto.md §5).

Remaining v4 failures on dev (3): a German grouping-vague list still read as one combined run
(R020.de-vague_grouping), and R065 in German and Chinese (one extra arm; one contrast against `base`
instead of B). Not tuned further: these are the bank's hardest items, and more rules for single dev
requests would fit dev rather than improve the Parser.

## 2b. Held-out pass (E5.1 Done), 2026-09-24

`v6-heldout`: v6, default model, 114 requests × 3 repetitions, run once with `--final`
($0.376). Every per-run threshold met — validity 100 %, intent 95.7 % (strict too), interventions
99.5 %, topology and metrics 100 %, ambiguity detection 82.2 % (95 % CI by concept 63–97 %), arm
structure 94.4 % (4 concepts) — but **`intent` agreement across the 3 runs is 93.9 % (107/114),
below the ≥ 95 % bar, so E5.1 is not Done.** Counting only requests with a gold intent does not
change the verdict (94.1 %, 80/85); that alternative reading is reported, not adopted, because it
was computed after seeing the result. Unstable: compare/counterfactual on "compare … with and
without" / "compared with NEW1 fully open" (R016.en-colloquial, R023.en-colloquial,
R023.es-no_accents), diagnose/describe on R073 and R073.ca, and two unintelligible R052 variants.
Ambiguity misses are all bare lists of changes (R042, R043 and the vague-grouping variants), the
same convention the user's first annotation missed. No temperature is set on any call, so the
provider's default sampling applies; that is the first suspect for the instability.

## 3. Bank fixes found by Parser runs

The v3 dev run exposed variants that did not say what their gold says; they were fixed before v4
(the v3 numbers are on the old texts):

| Variant | Defect |
|---|---|
| R004.en-telegraphic | "together" lost: the Parser rightly asked whether the two changes go together |
| R026.en-telegraphic | "each" lost: read as one combined treatment |
| R009.en-messy | "backed up" names no measure (gold `waiting_time`) |
| R054.ca, R054.es | the translation of an unintelligible request was intelligible |

2026-09-24: graded `intent` now also accepts `run` on the ten "simulate X and report Y" concepts
(`concepts.ALSO_ACCEPTED`); `intent_strict` is reported beside it. v6-dev re-scored: 99.4 % both
ways.

2026-09-24: R022 and R023 (held-out) reworded because even the user misread them ("add on top of
it"; a "compare it with" that is really an effect); gold unchanged. Their 8 variants were
regenerated ($0.0012) and read by hand: 6 fixed (generator framing leaked into R022.es-verbose,
"one-way" for "one-lane" in es/zh/ca, direction lost with "between", Catalan "vora"), noted per
variant in `variants.json`. The Parser has never run on them.

2026-09-24, after the first blind annotation: `intent` is now decided by what the user wants to
know, not by the verb (evaluating-resto.md §5). Gold changed `compare` → `counterfactual` on R016,
R023 (held-out) and R035 (dev). This is a gold change, not a Parser change: v4, which was tuned on
the old rule, is not re-scored against it until v5.

The same review read the 24 pilot variants in full (they had only had the pilot's sample review) and
fixed three typos (R003.de, R004.es, R005.ca).

## 4. Comparison runs

Same prompt (v4) and bank, another approved model, to check the bank tells a weak Parser from a
strong one (dev saturates at 100 % on five metrics with the default model, which alone could mean
the bank is easy).

| Run | Model | Result | Cost |
|---|---|---|---|
| `ministral-v4-dev`, 212 | `mistralai/ministral-3b-2512` | fails every E5.1 threshold: validity 78.8 % (45 runs out of budget), intent 78.0 %, interventions 50.8 %, metrics 73.4 %, ambiguity 61.4 %, arm structure 4.7 % (2/43), spurious ambiguity 67.9 %, consistency 11.1 % | $0.148 |

The bank discriminates: the gap is widest exactly where the conventions matter (arm structure,
ambiguity). It does not settle whether the default model's dev scores measure reading or
convention-following; that is what the blind annotation of held-out checks (evaluating-resto.md §5,
2026-09-24).
