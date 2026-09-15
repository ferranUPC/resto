"""`TlsProgramWriter` (E2.3, ADR-0007): static signal_program on a TlsTarget, WAUT switch,
byte-stable XML."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.writers.tls_program import TlsProgramWriter
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget, TlsTarget
from resto.domain.value_objects.time_window import TimeWindow

TLS = TlsTarget(tls_id="J4")


def signal_program(**overrides: object) -> Intervention:
    kwargs: dict[str, object] = {
        "type": InterventionType.SIGNAL_PROGRAM,
        "target": TLS,
        "window": TimeWindow(7 * 3600, 10 * 3600),
        "params": {"program_id": "1"},
    }
    kwargs.update(overrides)
    return Intervention(**kwargs)  # type: ignore[arg-type]


def test_supports_only_static_signal_program_on_a_tls_target() -> None:
    writer = TlsProgramWriter()
    assert writer.supports(signal_program())
    assert not writer.supports(
        Intervention(
            type=InterventionType.SIGNAL_PROGRAM,
            target=LaneTarget(edge_id="A0A1", lane_index=0),
            window=TimeWindow(0, 60),
            params={"program_id": "1"},
        )
    )
    assert not writer.supports(
        Intervention(type=InterventionType.SPEED_LIMIT, target=TLS, window=TimeWindow(0, 60))
    )


def test_write_produces_a_mechanism_and_matching_artifact_ref(tmp_path: Path) -> None:
    mechanism, ref = TlsProgramWriter().write(signal_program(), tmp_path)
    assert mechanism.file_kind == "tls_program"
    assert mechanism.path == (tmp_path / "waut_J4.add.xml").resolve()
    assert mechanism.path == ref.path
    assert ref.kind == "additional"
    assert mechanism.path.exists()


def test_write_rejects_a_missing_program_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        TlsProgramWriter().write(signal_program(params={}), tmp_path)


def test_write_rejects_an_unsupported_intervention(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        TlsProgramWriter().write(
            Intervention(type=InterventionType.SPEED_LIMIT, target=TLS, window=TimeWindow(0, 60)),
            tmp_path,
        )


def test_written_xml_has_the_waut_switch_and_defaults_the_original_program_to_zero(
    tmp_path: Path,
) -> None:
    mechanism, _ = TlsProgramWriter().write(signal_program(), tmp_path)
    text = mechanism.path.read_text(encoding="utf-8")
    assert '<WAUT id="waut_J4" startProg="0" refTime="0">' in text
    assert '<wautSwitch time="25200" to="1" />' in text
    assert '<wautSwitch time="36000" to="0" />' in text
    assert (
        '<wautJunction wautID="waut_J4" junctionID="J4" procedure="Explicit" synchron="false" />'
        in text
    )


def test_written_xml_honours_an_explicit_original_program_id(tmp_path: Path) -> None:
    mechanism, _ = TlsProgramWriter().write(
        signal_program(params={"program_id": "2", "original_program_id": "1"}), tmp_path
    )
    text = mechanism.path.read_text(encoding="utf-8")
    assert '<WAUT id="waut_J4" startProg="1" refTime="0">' in text
    assert '<wautSwitch time="25200" to="2" />' in text
    assert '<wautSwitch time="36000" to="1" />' in text


def test_authoring_is_deterministic(tmp_path: Path) -> None:
    a, _ = TlsProgramWriter().write(signal_program(), tmp_path / "a")
    b, _ = TlsProgramWriter().write(signal_program(), tmp_path / "b")
    assert a.path.read_text(encoding="utf-8") == b.path.read_text(encoding="utf-8")
