"""Sandbox for Builder scripts: lint (AST: only resto.traci_api imports), dry-run, execute."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.traci_script import DeclaredRule


class ScriptSandbox(Protocol):
    def lint(self, script: ArtifactRef) -> tuple[bool, str]: ...
    def declared_rules(self, script: ArtifactRef) -> tuple[DeclaredRule, ...]: ...
    def dry_run(
        self, script: ArtifactRef, sumocfg: ArtifactRef, steps: int, out_dir: Path
    ) -> tuple[bool, str]: ...
