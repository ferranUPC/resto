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


@dataclass(frozen=True, slots=True)
class AreaTooLarge:
    """The area to import is too large for one import (ADR-0045 §6): either its size is above the
    limit, refused before any download, or the network built from it has more edges than the limit
    (`edges` and `limit_edges` are then set, and the area itself may be within its limit)."""

    area_km2: float
    limit_km2: float
    edges: int | None = None
    limit_edges: int | None = None
    kind: Literal["area_too_large"] = "area_too_large"

    def __post_init__(self) -> None:
        if self.limit_km2 <= 0:
            raise ValueError("limit_km2 must be positive")
        if (self.edges is None) != (self.limit_edges is None):
            raise ValueError("edges and limit_edges go together")
        if self.edges is None or self.limit_edges is None:
            if self.area_km2 <= self.limit_km2:
                raise ValueError("area_km2 must be above limit_km2")
        elif self.edges <= self.limit_edges:
            raise ValueError("edges must be above limit_edges")

    @property
    def recommendation(self) -> str:
        if self.edges is not None:
            return (
                "Split the area into smaller ones, or import only the road classes the study needs."
            )
        return "Pick a smaller area, or an import profile with fewer road classes."


@dataclass(frozen=True, slots=True)
class PlaceNotBoundary:
    """The place name does not resolve to an administrative boundary, so it has no area to import
    (ADR-0045 §2). The geocoder's own words are in `NeedsUser.message`."""

    place: str
    kind: Literal["place_not_boundary"] = "place_not_boundary"

    def __post_init__(self) -> None:
        if not self.place.strip():
            raise ValueError("PlaceNotBoundary requires the place it names")

    @property
    def recommendation(self) -> str:
        return "Give a bounding box or a polygon for the area; this place has no boundary."


@dataclass(frozen=True, slots=True)
class UnsupportedRequirement:
    """The request needs something the network cannot hold, such as public transport stops
    (ADR-0045 §5)."""

    requirement: str
    kind: Literal["unsupported_requirement"] = "unsupported_requirement"

    def __post_init__(self) -> None:
        if not self.requirement.strip():
            raise ValueError("UnsupportedRequirement requires the requirement it names")

    @property
    def recommendation(self) -> str:
        return "Ask again without that requirement; the network does not hold it."


NeedsUserReason = (
    WindowMissing
    | DemandNotNamed
    | DemandNotObtainable
    | NetworkNotFound
    | SeveralCandidates
    | AreaTooLarge
    | PlaceNotBoundary
    | UnsupportedRequirement
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
