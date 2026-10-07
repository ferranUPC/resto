"""The fake setup: the shared test `World` run as a `Setup`, with scripted agents.

`FakeSetup.run` builds a `World` from the agent script registered for the golden path, stores the
path's prior state, runs `run_study` on its request and returns the study and the tracer's events.
`repetitions` is 3: `golden.framework.check` requires every repetition to meet the expected trace
and to equal the others, which exposes nondeterminism hidden in `World`.

`World` lives in `tests/unit/application/_world.py` and is imported from there, so the Executor
tests and the golden paths share one set of doubles. Run from the repository root.

Adding the script of a golden path
----------------------------------
One module per golden path in `golden/setups/fake/scripts/`, named like the path (`GoldenPath.name`,
for example `gp3.py`). It defines one module-level `SCRIPT = AgentScript(...)`. Nothing else is
edited: `scripts.discover` imports every module of the package, so there is no central list and two
tickets adding two paths never touch the same file. A path with no module fails with an error that
names the file to create.
"""

from golden.setups.fake.script import AgentScript
from golden.setups.fake.setup import FakeSetup

__all__ = ["AgentScript", "FakeSetup"]
