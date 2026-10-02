"""What a specialist's `obtain_*` step ends in (ADR-0037 §3): the id of something already stored,
a draft that code promotes (ADR-0001), or the need for the user to act. The specialist never writes
identity fields: `Found` names an id the Executor checks against the repositories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from resto.domain.value_objects.drafts import DemandDraft, NetworkDraft


@dataclass(frozen=True, slots=True)
class Found:
    """A stored network or demand that already answers the request."""

    id: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Found requires an id")


@dataclass(frozen=True, slots=True)
class WindowMissing:
    """No study window can be derived and the request gives no period (ADR-0037 §4)."""

    kind: Literal["window_missing"] = "window_missing"

    @property
    def recommendation(self) -> str:
        return "Say which period to simulate, or answer that it does not matter."


@dataclass(frozen=True, slots=True)
class DemandNotNamed:
    """The request says nothing about the traffic and there is no default demand (ADR-0035 §2)."""

    kind: Literal["demand_not_named"] = "demand_not_named"

    @property
    def recommendation(self) -> str:
        return "Say what traffic to simulate, for example a peak hour or random trips."


@dataclass(frozen=True, slots=True)
class DemandNotObtainable:
    """The requested demand is not stored and no capability can obtain it (ADR-0035 §3)."""

    demand_ref: str
    kind: Literal["demand_not_obtainable"] = "demand_not_obtainable"

    @property
    def recommendation(self) -> str:
        return "Ask for a demand that can be generated, or store the one you mean and ask again."


@dataclass(frozen=True, slots=True)
class NetworkNotFound:
    """No stored network matches the name and it gives no way to build one (ADR-0035 §6)."""

    network_ref: str
    kind: Literal["network_not_found"] = "network_not_found"

    @property
    def recommendation(self) -> str:
        return "Name a network that is stored, or describe one that can be generated."


@dataclass(frozen=True, slots=True)
class SeveralCandidates:
    """Several stored networks or demands match; `NeedsUser.candidates` lists them."""

    kind: Literal["several_candidates"] = "several_candidates"

    @property
    def recommendation(self) -> str:
        return "Ask again, naming the one you mean."


NeedsUserReason = (
    WindowMissing | DemandNotNamed | DemandNotObtainable | NetworkNotFound | SeveralCandidates
)


@dataclass(frozen=True, slots=True)
class FoundItem:
    """Something the specialist already found when it had to stop."""

    what: Literal["network", "demand"]
    id: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("a FoundItem requires an id")


@dataclass(frozen=True, slots=True)
class NeedsUser:
    """The user must act: the specialist is done with this request (ADR-0037 §4).

    `message` is the specialist's account of what it was asked, what it cannot do and why. The
    code derives the default recommendation from `reason`; `advice` is the specialist's own, on
    top of it."""

    reason: NeedsUserReason
    message: str
    candidates: tuple[str, ...] = ()
    found: tuple[FoundItem, ...] = ()
    advice: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("NeedsUser requires a message")
        if isinstance(self.reason, SeveralCandidates) and len(self.candidates) < 2:
            raise ValueError("several_candidates needs at least two candidates")

    @property
    def recommendations(self) -> tuple[str, ...]:
        """The default recommendation for the reason, then the specialist's `advice`."""
        return (self.reason.recommendation, *self.advice)


NetworkOutcome = Found | NetworkDraft | NeedsUser
DemandOutcome = Found | DemandDraft | NeedsUser
