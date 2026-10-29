"""Size and concentration of a diff, for the PR body and the Concentration reviewer.

    python scripts/diff_concentration.py origin/master

Prints lines added and removed per area (src, tests, other), then the files and directories
that hold the most added lines, with their cumulative share. Reads git only; changes nothing.
"""

from __future__ import annotations

import subprocess
import sys
from collections import defaultdict
from pathlib import PurePosixPath

TEST_ROOTS = ("tests", "conformance", "verify", "golden")
TOP_FILES = 10
TOP_DIRECTORIES = 5


def parse_numstat(text: str) -> dict[str, tuple[int, int]]:
    """Path to (added, removed); binary files ("-") are skipped."""
    changes: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        added, removed, path = line.split("\t", 2)
        if added != "-":
            changes[path] = (int(added), int(removed))
    return changes


def area(path: str) -> str:
    root = PurePosixPath(path).parts[0]
    if root == "src":
        return "src"
    return "tests" if root in TEST_ROOTS else "other"


def _ranked(totals: dict[str, int], limit: int) -> list[str]:
    grand = sum(totals.values()) or 1
    running = 0
    rows = []
    for name, added in sorted(totals.items(), key=lambda item: -item[1])[:limit]:
        running += added
        rows.append(f"  +{added:<5} {running * 100 // grand:>3}%  {name}")
    return rows


def summarise(changes: dict[str, tuple[int, int]]) -> str:
    areas: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    files: dict[str, int] = {}
    directories: dict[str, int] = defaultdict(int)
    for path, (added, removed) in changes.items():
        areas[area(path)][0] += added
        areas[area(path)][1] += removed
        if area(path) != "other":
            files[path] = added
            directories[str(PurePosixPath(path).parent)] += added
    lines = ["Added and removed lines"]
    for name in ("src", "tests", "other"):
        added, removed = areas[name]
        lines.append(f"  {name:<6} +{added} -{removed}")
    lines += [
        "",
        f"Files with most added lines in src and tests (cumulative share of {sum(files.values())})",
    ]
    lines += _ranked(files, TOP_FILES)
    lines += ["", "Directories"]
    lines += _ranked(directories, TOP_DIRECTORIES)
    return "\n".join(lines)


def main(fixed_point: str) -> None:
    diff = subprocess.run(
        ["git", "diff", "--numstat", f"{fixed_point}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    print(summarise(parse_numstat(diff.stdout)))


if __name__ == "__main__":
    main(sys.argv[1])
