from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef


@dataclass(frozen=True, slots=True)
class DeclaredRule:
    """A rule registered through traci_api's `at_time(...)` / `when(...)`, as data."""

    trigger: str
    action: str


@dataclass(frozen=True, slots=True)
class TraciScript:
    artifact: ArtifactRef
    api_version: str
    declared_rules: tuple[DeclaredRule, ...] = ()
    lint_ok: bool = False
    dry_run_ok: bool = False

    @property
    def is_runnable(self) -> bool:
        return self.lint_ok and self.dry_run_ok
