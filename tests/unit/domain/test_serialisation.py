"""DoD §4.9: `validate_json(dump_json(x)) == x` for every domain type, invariants firing."""

import pytest
from pydantic import TypeAdapter

from tests.unit.domain._samples import SAMPLES, domain_dataclasses

TYPES = sorted(SAMPLES, key=lambda t: t.__name__)


def test_every_domain_dataclass_has_a_sample() -> None:
    """Without this, a new type would silently escape the round-trip suite below."""
    missing = {t.__name__ for t in domain_dataclasses() - set(SAMPLES)}
    assert not missing, f"no sample for: {sorted(missing)}"


def test_samples_do_not_cover_types_that_no_longer_exist() -> None:
    stale = {t.__name__ for t in set(SAMPLES) - domain_dataclasses()}
    assert not stale, f"sample for a type outside resto.domain: {sorted(stale)}"


@pytest.mark.parametrize("dtype", TYPES, ids=lambda t: t.__name__)
def test_round_trips_through_json(dtype: type) -> None:
    adapter = TypeAdapter(dtype)
    sample = SAMPLES[dtype]()
    assert adapter.validate_json(adapter.dump_json(sample)) == sample


@pytest.mark.parametrize("dtype", TYPES, ids=lambda t: t.__name__)
def test_exports_a_json_schema(dtype: type) -> None:
    assert TypeAdapter(dtype).json_schema()
