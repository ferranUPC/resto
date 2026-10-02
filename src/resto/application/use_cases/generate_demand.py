"""Demand Generator: ObtainDemandTask -> calibration loop via run_simulation
-> DemandDraft -> promoted Demand.

Placeholder: signature and behaviour defined in docs/tfm-architecture-and-dod.md (v0.3).

Promotion rule (ADR-0035, built and tested in E6.2): the promoted `Demand` copies the draft's
`description` and `labels` unchanged, then adds `spec.profile.value` to `labels`. The profile goes
in for every profile, `custom` included.
"""

from __future__ import annotations


def generate_demand(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
    raise NotImplementedError("generate_demand: see docs/tfm-architecture-and-dod.md §2.2/§2.4")
