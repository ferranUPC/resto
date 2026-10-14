"""The typemaps come from the installed SUMO package by absolute path, never from `SUMO_HOME`
(ADR-0010, ADR-0045)."""

from __future__ import annotations

import os

from resto.adapters.sumo.typemaps import typemap_dir


def test_the_typemap_directory_is_absolute_and_holds_the_osm_typemaps() -> None:
    directory = typemap_dir()

    assert directory.is_absolute()
    assert (directory / "osmNetconvert.typ.xml").is_file()
    assert (directory / "osmNetconvertBicycle.typ.xml").is_file()


def test_it_does_not_need_sumo_home() -> None:
    assert "SUMO_HOME" not in os.environ
