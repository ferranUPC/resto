"""`write_sumocfg` writer (E2.1, ADR-0017): relative paths, byte-stable rendering, round trip
through `parse_settings`, and SUMO actually loading what it writes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from resto.adapters.sumo.writers.sumocfg import (
    SumocfgFileWriter,
    parse_settings,
    render_sumocfg,
    write_edgedata_additional,
)
from resto.application.ports.writers import SimulationSettings

DEV_NET_DIR = Path(__file__).resolve().parents[5] / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
LOW_ROUTES = DEV_NET_DIR / "demand" / "low.rou.xml"


def settings(**overrides: object) -> SimulationSettings:
    kwargs: dict[str, object] = {"net_file": NET, "route_files": (LOW_ROUTES,), "end": 600.0}
    kwargs.update(overrides)
    return SimulationSettings(**kwargs)  # type: ignore[arg-type]


# --- SimulationSettings invariants ----------------------------------------------------------------


def test_settings_require_a_route_file() -> None:
    with pytest.raises(ValueError):
        settings(route_files=())


def test_settings_reject_an_end_before_begin() -> None:
    with pytest.raises(ValueError):
        settings(begin=100.0, end=50.0)


def test_settings_reject_a_non_positive_step_length() -> None:
    with pytest.raises(ValueError):
        settings(step_length=0.0)


# --- rendering ------------------------------------------------------------------------------------


def test_rendered_cfg_uses_paths_relative_to_the_cfg_directory(tmp_path: Path) -> None:
    text = render_sumocfg(settings(), tmp_path)

    assert 'value="/' not in text, "every path must be relative to the cfg directory"
    assert text.count("dev-net.net.xml") == 1
    assert "demand/low.rou.xml" in text


def test_rendered_cfg_carries_no_seed_and_no_output_section(tmp_path: Path) -> None:
    text = render_sumocfg(settings(), tmp_path)

    assert "<random_number>" not in text
    assert "<output>" not in text


def test_rendering_is_byte_stable_for_identical_settings(tmp_path: Path) -> None:
    assert render_sumocfg(settings(), tmp_path) == render_sumocfg(settings(), tmp_path)


def test_seed_and_outputs_render_into_their_sumo_sections(tmp_path: Path) -> None:
    text = render_sumocfg(
        settings(),
        tmp_path,
        seed=7,
        outputs={"tripinfo-output": "tripinfo.xml"},
        report={"no-step-log": "true"},
    )

    assert '<seed value="7" />' in text
    assert '<tripinfo-output value="tripinfo.xml" />' in text
    assert '<no-step-log value="true" />' in text


def test_integral_numbers_render_without_a_decimal_point(tmp_path: Path) -> None:
    text = render_sumocfg(settings(begin=0.0, end=3600.0, step_length=0.5), tmp_path)

    assert '<begin value="0" />' in text
    assert '<end value="3600" />' in text
    assert '<step-length value="0.5" />' in text


# --- writer + parse round trip --------------------------------------------------------------------


def test_writer_returns_an_artifact_whose_hash_is_the_file_content(tmp_path: Path) -> None:
    ref = SumocfgFileWriter().write(settings(), tmp_path, "scenario.sumocfg")

    assert ref.path == (tmp_path / "scenario.sumocfg").resolve()
    assert ref.kind == "sumocfg"
    assert len(ref.content_hash) == 64


def test_same_settings_in_two_directories_give_the_same_hash(tmp_path: Path) -> None:
    a = SumocfgFileWriter().write(settings(), tmp_path / "a", "s.sumocfg")
    b = SumocfgFileWriter().write(settings(), tmp_path / "b", "s.sumocfg")

    assert a.content_hash == b.content_hash


def test_parse_settings_round_trips_the_written_cfg_with_absolute_paths(tmp_path: Path) -> None:
    extra = tmp_path / "closure.add.xml"
    extra.write_text("<additional/>")
    original = settings(additional_files=(extra,), begin=60.0, end=660.0, time_to_teleport=120.0)
    ref = SumocfgFileWriter().write(original, tmp_path, "scenario.sumocfg")

    parsed = parse_settings(ref.path)

    assert parsed.net_file == NET.resolve()
    assert parsed.route_files == (LOW_ROUTES.resolve(),)
    assert parsed.additional_files == (extra.resolve(),)
    assert (parsed.begin, parsed.end, parsed.step_length, parsed.time_to_teleport) == (
        60.0,
        660.0,
        1.0,
        120.0,
    )


def test_parse_settings_rejects_a_cfg_with_a_seed_or_outputs(tmp_path: Path) -> None:
    cfg = tmp_path / "run.sumocfg"
    cfg.write_text(render_sumocfg(settings(), tmp_path, seed=1))

    with pytest.raises(ValueError, match="random_number"):
        parse_settings(cfg)


def test_parse_settings_rejects_a_cfg_without_routes(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.sumocfg"
    cfg.write_text('<configuration><input><net-file value="n.xml"/></input></configuration>')

    with pytest.raises(ValueError, match="route-files"):
        parse_settings(cfg)


# --- SUMO loads it --------------------------------------------------------------------------------


def test_sumo_loads_the_written_cfg(tmp_path: Path) -> None:
    ref = SumocfgFileWriter().write(settings(end=1.0), tmp_path, "scenario.sumocfg")

    proc = subprocess.run(
        ["sumo", "-c", str(ref.path), "--no-step-log"], capture_output=True, text=True, cwd="/"
    )

    assert proc.returncode == 0, proc.stderr


def test_edgedata_additional_declares_the_period_and_output_file(tmp_path: Path) -> None:
    path = write_edgedata_additional(tmp_path, 300.0, "edgedata.xml")

    assert path.read_text() == (
        "<additional>\n"
        '    <edgeData id="resto_edgedata" freq="300" file="edgedata.xml" />\n'
        "</additional>\n"
    )
