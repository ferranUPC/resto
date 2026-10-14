"""Entry point: `python -m golden.run --setup fake`, from the repository root.

Runs every golden path on the chosen setup and prints a pass or a diff per path. Exits 1 if any
path differs.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from golden.framework.setup import check
from golden.paths import discover
from golden.setups.fake import FakeSetup

AGENTIC_REJECTED = (
    "the agentic setup is not implemented: the model and limits per agent arrive with E12.1. "
    "No model call was made. Read docs/llm-cost-policy.md before any real run."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m golden.run", description=__doc__)
    parser.add_argument("--setup", choices=("fake", "agentic"), required=True)
    args = parser.parse_args(argv)
    if args.setup == "agentic":
        print(AGENTIC_REJECTED, file=sys.stderr)
        return 2
    setup = FakeSetup()
    failed = 0
    for path in discover():
        try:
            diff = check(setup, path)
            detail = "" if diff.ok else diff.render()
        except Exception as error:
            detail = f"{type(error).__name__}: {error}"
        if detail:
            failed += 1
            print(f"FAIL {path.name}")
            print("\n".join(f"  {line}" for line in detail.splitlines()))
        else:
            print(f"PASS {path.name} ({setup.repetitions} repetitions)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
