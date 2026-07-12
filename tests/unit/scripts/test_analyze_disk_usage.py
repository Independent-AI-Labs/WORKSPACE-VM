"""Unit tests for analyze_disk_usage utility."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from workspace.scripts.utils import analyze_disk_usage as adu


def test_human_readable_kb() -> None:
    assert adu.human_readable(512) == "512.00 KB"


def test_human_readable_gb() -> None:
    assert "GB" in adu.human_readable(1024 * 1024)


def test_human_readable_pb() -> None:
    huge = 1024**5
    assert adu.human_readable(huge).endswith("PB")


def test_run_du_same_fs_adds_x_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str]] = []

    def _fake_run(
        cmd: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "1\t/tmp\n", "")

    monkeypatch.setattr(adu.subprocess, "run", _fake_run)
    adu._run_du("/tmp", same_fs=True)
    assert "-x" in captured[0]


def test_run_du_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        adu.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "du")),
    )
    assert adu._run_du("/tmp", same_fs=False) is None


def test_analyze_du_failure_returns_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adu, "_run_du", lambda *_a, **_k: None)
    adu.analyze(str(tmp_path))


def test_analyze_missing_path(capsys) -> None:
    adu.analyze("/nonexistent-path-xyz-12345")
    assert "does not exist" in capsys.readouterr().out


def test_analyze_skips_unparseable_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    du_output = f"notint\t{tmp_path / 'ok'}\n2048\t{tmp_path}\n"
    monkeypatch.setattr(adu, "_run_du", lambda *_a, **_k: du_output)
    adu.analyze(str(tmp_path))
    err = capsys.readouterr().err
    assert "unparseable" in err


def test_analyze_no_child_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    du_output = f"2048\t{tmp_path}\n"
    monkeypatch.setattr(adu, "_run_du", lambda *_a, **_k: du_output)
    adu.analyze(str(tmp_path))
    assert "No readable" in capsys.readouterr().out


def test_analyze_prints_top_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    child = tmp_path / "child"
    child.mkdir()
    du_output = f"\n1024\t{child}\n2048\t{tmp_path}\n"
    monkeypatch.setattr(adu, "_run_du", lambda *_a, **_k: du_output)
    adu.analyze(str(tmp_path))
    output = capsys.readouterr().out
    assert "Scanning" in output
    assert "child" in output
