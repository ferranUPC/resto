"""GP-9: the parser flags the request as ambiguous, so nothing is planned."""

from dataclasses import replace

from tests.unit.application._world import DESCRIBE

from golden.setups.fake.script import AgentScript

SCRIPT = AgentScript(
    question=replace(
        DESCRIBE,
        ambiguities=("Improve delays or emissions? The two readings need different studies.",),
    )
)
