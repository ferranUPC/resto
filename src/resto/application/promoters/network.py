"""Network Author promotion: an already-run `AgentRun[NetworkDraft]` -> a `Network` (DoD §2.2, §2.4;
ADR-0001, ADR-0042 §5, ADR-0045 §9).

One promoter for a created and a derived network: the context says which (an `ObtainNetworkTask`,
or a `NetworkTask` with a `base_network_id`). The step executor that called the Network Author
stores what it returns.

Promotion order (ADR-0001):
  1. syntactic - the agent returned a `NetworkDraft` (its invariants ran at construction).
  2. semantic  - the recipe fits the task (a derivation of the task's base network, or a created
                 network); a generated network carries no `netconvert` options; the sanity check
                 passed with the task's threshold or the failure is in `unresolved[]`; and the
                 recipe, replayed here without an LLM, gives the `content_hash` the draft claims.
  3. construct - `network_id` is that hash, `derived_from` the recipe's base network, and an
                 obtained network is labelled with the reference it was asked for, so the next
                 `find_network` of that name finds it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from resto.application.ports.llm import AgentRun
from resto.application.ports.sumo import (
    NetBuildError,
    NetconvertRunner,
    PlainNetEditor,
    UnresolvableEdit,
)
from resto.application.promotion import DraftRejected, require_draft
from resto.domain.entities.network import Network
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.drafts import NetworkDraft
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import GeneratedNetwork
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask


class NetworkPromoter:
    """A promoter reads and stores nothing (ADR-0042 §5): the base network of a derivation arrives
    as an argument, loaded by the step.

    One exception to ADR-0042 §5, by ADR-0045 §9: replaying the recipe to check its `content_hash`
    runs `netconvert` and the plain-XML edits in a temporary directory. It is the check itself, and
    it writes nothing the study keeps: the temporary directory is gone when `promote` returns."""

    def __init__(self, runner: NetconvertRunner, editor: PlainNetEditor) -> None:
        self._runner = runner
        self._editor = editor

    def promote(
        self,
        run: AgentRun[NetworkDraft],
        context: NetworkTask | ObtainNetworkTask,
        base_net: ArtifactRef | None = None,
    ) -> Network:
        """`base_net` is the `.net.xml` of `context.base_network_id`, required for a derivation."""
        draft = require_draft(run, "network_author")
        recipe = draft.recipe
        _check_recipe_fits(recipe, context)
        if draft.is_silent_failure(context.min_scc_ratio):
            raise DraftRejected(
                "the sanity check failed and unresolved[] is empty: report what could not be fixed"
            )
        replayed = self._replay(recipe, base_net)
        if replayed.content_hash != draft.net_artifact.content_hash:
            raise DraftRejected(
                f"replaying the recipe gives content_hash {replayed.content_hash}, "
                f"the draft claims {draft.net_artifact.content_hash}"
            )
        return Network(
            network_id=draft.net_artifact.content_hash,
            net_xml=draft.net_artifact,
            recipe=recipe,
            sanity_report=draft.sanity_report,
            derived_from=recipe.base_network_id,
            probe_report=draft.probe_report,
            label=context.network_ref if isinstance(context, ObtainNetworkTask) else None,
        )

    def _replay(self, recipe: NetworkRecipe, base_net: ArtifactRef | None) -> ArtifactRef:
        """The recipe rebuilt from scratch in a scratch directory (nothing of it is kept)."""
        with tempfile.TemporaryDirectory(prefix="resto-replay-") as scratch:
            root = Path(scratch)
            try:
                return self._rebuild(recipe, base_net, root)
            except NetBuildError as error:
                raise DraftRejected(f"the recipe does not build: {error}") from error
            except UnresolvableEdit as error:
                needed = error.issue.needed_tool
                raise DraftRejected(
                    f"the recipe holds an edit that cannot be applied: {error}"
                    + (f" (needs the tool {needed!r}); put it in unresolved[]" if needed else "")
                ) from error

    def _rebuild(
        self, recipe: NetworkRecipe, base_net: ArtifactRef | None, root: Path
    ) -> ArtifactRef:
        if recipe.base_network_id is not None:
            if base_net is None:
                raise ValueError("replaying a derivation needs the .net.xml of its base network")
            return self._edit(base_net, recipe, root)
        if isinstance(recipe.source, GeneratedNetwork):
            net = self._runner.generate(recipe.source, root / "generated")
        else:
            net = self._runner.build(
                recipe.osm_snapshot, None, recipe.netconvert_options, root / "imported"
            )
        return self._edit(net, recipe, root) if recipe.plain_edits else net

    def _edit(self, net: ArtifactRef, recipe: NetworkRecipe, root: Path) -> ArtifactRef:
        plain = self._runner.export_plain(net, root / "plain")
        for modification in recipe.plain_edits:
            self._editor.apply(plain, modification)
        return self._runner.build(None, plain, recipe.netconvert_options, root / "edited")


def _check_recipe_fits(recipe: NetworkRecipe, context: NetworkTask | ObtainNetworkTask) -> None:
    if isinstance(context, NetworkTask):
        if recipe.base_network_id != context.base_network_id:
            raise DraftRejected(
                f"the recipe must derive from base network {context.base_network_id!r}, "
                f"not {recipe.base_network_id!r}"
            )
    elif recipe.is_derivation:
        raise DraftRejected("an obtained network is not a derivation: the recipe names a base")
    if isinstance(recipe.source, GeneratedNetwork) and recipe.netconvert_options:
        raise DraftRejected(
            "netconvert_options on a generated network would be ignored: "
            "a generated network takes its typed parameters only"
        )
