import dataclasses

from resto.domain.services.reproducibility import reproducibility_hash
from resto.domain.value_objects.artifact_ref import ArtifactRef
from tests.unit.domain._fixtures import artifact


def _artifacts(digest: str = "ed1") -> tuple[ArtifactRef, ...]:
    return (
        artifact("run.sumocfg", "cfg1", "sumocfg"),
        artifact("edgedata.xml", digest, "edgedata"),
        artifact("statistics.xml", "st-with-clock", "statistics"),
    )


def test_content_hash_covers_only_the_deterministic_artifacts() -> None:
    with_clock_a = _artifacts() + (artifact("summary.xml", "sum-1", "summary"),)
    with_clock_b = tuple(
        dataclasses.replace(a, content_hash="other-clock")
        if a.kind in ("statistics", "summary")
        else a
        for a in with_clock_a
    )
    other_edgedata = _artifacts("ed2")

    assert reproducibility_hash(with_clock_a) == reproducibility_hash(with_clock_b)
    assert reproducibility_hash(with_clock_a) != reproducibility_hash(other_edgedata)


def test_the_script_is_part_of_an_online_runs_hash() -> None:
    batch = _artifacts()
    online = batch + (artifact("script.py", "script1", "script"),)
    other_script = batch + (artifact("script.py", "script2", "script"),)

    assert reproducibility_hash(online) != reproducibility_hash(batch)
    assert reproducibility_hash(online) != reproducibility_hash(other_script)
