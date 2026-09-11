from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MIN_SCC_RATIO = 0.95


@dataclass(frozen=True, slots=True)
class SanityReport:
    largest_scc_ratio: float
    zero_length_edges: int
    all_reachable_from_fringe: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.largest_scc_ratio <= 1.0:
            raise ValueError("largest_scc_ratio must be in [0, 1]")
        if self.zero_length_edges < 0:
            raise ValueError("zero_length_edges must be >= 0")

    def passes(self, min_scc_ratio: float = DEFAULT_MIN_SCC_RATIO) -> bool:
        return (
            self.largest_scc_ratio >= min_scc_ratio
            and self.zero_length_edges == 0
            and self.all_reachable_from_fringe
        )
