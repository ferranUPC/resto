from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MIN_SCC_RATIO = 0.95


@dataclass(frozen=True, slots=True)
class SanityReport:
    largest_scc_ratio: float
    zero_length_edges: int
    all_reachable_from_fringe: bool
    through_traffic_ratio: float
    """Share of the edges that lie on a path from an entry to an exit (ADR-0048). It is what
    `passes` compares with its threshold; `largest_scc_ratio` is only reported."""

    def __post_init__(self) -> None:
        if not 0.0 <= self.largest_scc_ratio <= 1.0:
            raise ValueError("largest_scc_ratio must be in [0, 1]")
        if not 0.0 <= self.through_traffic_ratio <= 1.0:
            raise ValueError("through_traffic_ratio must be in [0, 1]")
        if self.zero_length_edges < 0:
            raise ValueError("zero_length_edges must be >= 0")

    def passes(self, min_scc_ratio: float = DEFAULT_MIN_SCC_RATIO) -> bool:
        """`min_scc_ratio` keeps the name the plans and tasks carry; since ADR-0048 it is the
        threshold of `through_traffic_ratio`."""
        return (
            self.through_traffic_ratio >= min_scc_ratio
            and self.zero_length_edges == 0
            and self.all_reachable_from_fringe
        )
