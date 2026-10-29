---
name: code-review
description: Three-axis review of a branch or PR (Standards, Spec, Concentration). Use for any review of this repo's diff, in place of mattpocock-skills:code-review.
disable-model-invocation: true
---

# Code review

`mattpocock-skills:code-review` runs the Standards and Spec axes. This skill adds a third, Concentration, and runs the three in parallel.

## 1. Pin the fixed point

Whatever the user named, or `origin/master`. Confirm `git rev-parse <fixed-point>` resolves and `git diff --stat <fixed-point>...HEAD` is not empty.

## 2. Measure

Run `python scripts/diff_concentration.py <fixed-point>`. The table is the Concentration reviewer's input and goes into the final report as is.

## 3. Spawn three reviewers in one message

1. Invoke `mattpocock-skills:code-review` with the fixed point. It spawns Standards and Spec.
2. In the same message, spawn the Concentration reviewer (below).

All three are on the allowlist of `docs/agents/subagents.md`.

### Concentration reviewer brief

Read-only. Give it the diff command, the table from step 2 and this brief:

> Find code the diff can lose without changing behaviour. Start where the lines are: take the rows of the table until they cover 60% of the added lines, and read those files first. For each, look for duplicated logic, dead branches no caller reaches, speculative parameters, a class that only delegates, and tests that repeat a fixture or assert internals instead of the contract. Smaller files only matter when a cut there removes a whole module.
>
> A cut counts only with all three: `file:lines`, the lines it recovers, and the existing test that still proves the behaviour. A cut that needs a test changed goes in a separate list. Report a table sorted by lines recovered. Under 400 words.

## 4. Report

Three headings, `## Standards`, `## Spec`, `## Concentration`, each verbatim or lightly cleaned. Do not merge or rerank across axes. End with the findings per axis and the largest recoverable cut.
