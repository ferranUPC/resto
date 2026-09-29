"""`FilesystemRunDirectories`: the two cases the `run_simulation` tests only reach indirectly."""

from __future__ import annotations

from pathlib import Path

from resto.adapters.sumo.run_directories import FilesystemRunDirectories
from tests.unit.domain._fixtures import artifact


def test_a_leftover_canonical_directory_is_replaced(tmp_path: Path) -> None:
    staging = tmp_path / "r1.study-1"
    canonical = tmp_path / "r1"
    dirs = FilesystemRunDirectories()
    dirs.prepare(staging)
    (staging / "edgedata.xml").write_text("new")
    canonical.mkdir()
    (canonical / "stale.xml").write_text("old")

    (promoted,) = dirs.promote(staging, canonical, [artifact(str(staging / "edgedata.xml"))])

    assert promoted.path == canonical / "edgedata.xml"
    assert (canonical / "edgedata.xml").read_text() == "new"
    assert not (canonical / "stale.xml").exists()
    assert not staging.exists()


def test_a_ref_outside_the_staging_directory_is_returned_unchanged(tmp_path: Path) -> None:
    staging = tmp_path / "r1.study-1"
    dirs = FilesystemRunDirectories()
    dirs.prepare(staging)
    outside = artifact(str(tmp_path / "elsewhere" / "net.xml"), "n1", "net")

    (promoted,) = dirs.promote(staging, tmp_path / "r1", [outside])

    assert promoted == outside
