---
name: pr
description: Write the body of a pull request for this repo. Use whenever a PR is opened or its body updated.
---

# PR

Write the body with the template of `mattpocock-skills:pr`, then add a `## Size` section between `## Summary` and `## Evidence`.

## Size

1. Run `python scripts/diff_concentration.py origin/master`.
2. Paste its first block (added and removed lines for `src`, `tests` and `other`) as a code block.
3. Name the file with the most added lines in `src` and say in one sentence what it does that no existing module did. If the answer is "nothing new", say so: that is the first thing the reviewer will cut.
