"""`launch`: real SUMO for the normal case, fake binaries on the PATH for the rest."""

from __future__ import annotations

import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from resto.adapters.sumo import sumo_process
from resto.adapters.sumo.sumo_process import SumoVersionError, launch


@pytest.fixture(autouse=True)
def fresh_version_cache() -> Iterator[None]:
    sumo_process._version_cache.clear()
    yield
    sumo_process._version_cache.clear()


def _fake_tool(bin_dir: Path, name: str, version: str, body: str = "") -> Path:
    """A script that counts its calls in `<name>.calls`, reports `version`, then runs `body`."""
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / name
    script.write_text(
        "#!/bin/sh\n"
        f'printf \'%s\\n\' "$*" >> "{bin_dir}/{name}.calls"\n'
        f'if [ "$1" = "--version" ]; then echo "Eclipse SUMO {name} {version}"; exit 0; fi\n'
        f"{body}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return bin_dir / f"{name}.calls"


def _on_path(monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> None:
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")


def test_a_real_sumo_launch_is_ok(tmp_path: Path) -> None:
    result = launch("sumo", ["--help"], tmp_path, seed=1)

    assert result.ok is True


def test_the_files_a_tool_writes_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tool(tmp_path / "bin", "duarouter", "1.27.1", "echo x > out.xml")
    _on_path(monkeypatch, tmp_path / "bin")
    work = tmp_path / "work"
    work.mkdir()

    result = launch("duarouter", [], work, seed=1)

    assert result.ok is True
    assert result.files == (work / "out.xml",)


def test_another_sumo_version_raises_before_anything_is_launched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_tool(tmp_path / "bin", "sumo", "1.20.0")
    _on_path(monkeypatch, tmp_path / "bin")

    with pytest.raises(SumoVersionError, match=r"1\.20\.0.*1\.27\.1"):
        launch("sumo", ["-c", "x"], tmp_path, seed=1)

    assert calls.read_text().splitlines() == ["--version"]


def test_a_failing_tool_is_a_result_with_the_stderr_rule_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = 'echo "Warning: noise" >&2; echo "Error: boom" >&2; exit 1'
    _fake_tool(tmp_path / "bin", "duarouter", "1.27.1", body)
    _on_path(monkeypatch, tmp_path / "bin")

    result = launch("duarouter", [], tmp_path, seed=1)

    assert result.ok is False
    assert result.message == "Error: boom"


def test_a_silent_failure_reports_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tool(tmp_path / "bin", "duarouter", "1.27.1", "exit 3")
    _on_path(monkeypatch, tmp_path / "bin")

    result = launch("duarouter", [], tmp_path, seed=1)

    assert result.ok is False
    assert "3" in result.message


def test_a_missing_binary_is_a_failed_result(tmp_path: Path) -> None:
    result = launch("sumo-does-not-exist", [], tmp_path, seed=1)

    assert result.ok is False
    assert result.message


def test_the_version_is_read_once_per_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _fake_tool(tmp_path / "bin", "duarouter", "1.27.1")
    _on_path(monkeypatch, tmp_path / "bin")

    for _ in range(3):
        assert launch("duarouter", ["a"], tmp_path, seed=1).ok

    assert calls.read_text().splitlines().count("--version") == 1


def test_sumo_keeps_the_seed_in_its_config_and_other_tools_get_it_on_the_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sumo_calls = _fake_tool(tmp_path / "bin", "sumo", "1.27.1")
    du_calls = _fake_tool(tmp_path / "bin", "duarouter", "1.27.1")
    _on_path(monkeypatch, tmp_path / "bin")

    launch("sumo", ["-c", "run.sumocfg"], tmp_path, seed=7)
    launch("duarouter", ["-n", "x"], tmp_path, seed=7)

    assert sumo_calls.read_text().splitlines()[-1] == "-c run.sumocfg"
    assert du_calls.read_text().splitlines()[-1] == "-n x --seed 7"


def test_checked_version_reads_the_real_binary_once_and_returns_the_pinned_version() -> None:
    assert sumo_process.checked_version("sumo") == "1.27.1"


def test_checked_version_raises_on_another_version_and_on_a_missing_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tool(tmp_path / "bin", "sumo", "1.20.0")
    _on_path(monkeypatch, tmp_path / "bin")

    with pytest.raises(SumoVersionError, match=r"1\.20\.0.*1\.27\.1"):
        sumo_process.checked_version("sumo")
    with pytest.raises(SumoVersionError):
        sumo_process.checked_version("sumo-does-not-exist")
