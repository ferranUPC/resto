from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SanityReport:
    largest_scc_ratio: float
    zero_length_edges: int
    all_reachable_from_fringe: bool

    @property
    def passes(self) -> bool:
        return (
            self.largest_scc_ratio >= 0.95
            and self.zero_length_edges == 0
            and self.all_reachable_from_fringe
        )
