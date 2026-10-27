"""Unit tests for persistent QEMU state."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workspace.cli.hypervisor import qemu_state as qs

_SSH_PORT = 55222


def test_ensure_state_writes_persistent_default(tmp_path: Path) -> None:
    state = qs.ensure_state(tmp_path, profile="full-ci", mode="persistent")
    assert state.mode == "persistent"
    assert state.profile == "full-ci"
    assert qs.state_path(tmp_path).is_file()


def test_ensure_state_preserves_existing(tmp_path: Path) -> None:
    qs.ensure_state(tmp_path, profile="guard", mode="ephemeral")
    state = qs.ensure_state(tmp_path, profile="full-ci", mode="persistent")
    assert state.profile == "guard"
    assert state.mode == "ephemeral"


def test_mark_started_and_stopped(tmp_path: Path) -> None:
    qs.ensure_state(tmp_path, profile="none", mode="persistent")
    qs.mark_started(tmp_path, ssh_port=_SSH_PORT, pid_start="Thu Oct 23")
    state = qs.load_state(tmp_path)
    assert state is not None
    assert state.ssh_port == _SSH_PORT
    assert state.pid_start == "Thu Oct 23"
    assert state.last_started_at is not None
    qs.mark_stopped(tmp_path, error="cleanup")
    stopped = qs.load_state(tmp_path)
    assert stopped is not None
    assert stopped.last_error == "cleanup"
    assert stopped.pid_start is None


def test_is_persistent_defaults_true_without_state(tmp_path: Path) -> None:
    assert qs.is_persistent(tmp_path) is True


def test_is_persistent_reads_state(tmp_path: Path) -> None:
    qs.ensure_state(tmp_path, profile="none", mode="ephemeral")
    assert qs.is_persistent(tmp_path) is False


def test_invalid_state_raises(tmp_path: Path) -> None:
    qs.state_path(tmp_path).write_text("not-json")
    with pytest.raises(qs.QemuStateError, match="invalid state file"):
        qs.load_state(tmp_path)


def test_process_identity_reads_ps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qs.subprocess,
        "run",
        MagicMock(
            return_value=subprocess.CompletedProcess(
                "ps", 0, "Thu Oct 23 10:00:00\n", ""
            )
        ),
    )
    assert qs.process_identity(1234) == "Thu Oct 23 10:00:00"


def test_process_identity_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qs.subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "ps")),
    )
    assert qs.process_identity(1234) is None


def test_process_matches_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qs.os, "kill", MagicMock(return_value=None))
    monkeypatch.setattr(qs, "process_identity", lambda _pid: "same")
    assert qs.process_matches(1234, "same") is True
    assert qs.process_matches(1234, "different") is False


def test_process_matches_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qs.os, "kill", MagicMock(side_effect=ProcessLookupError))
    assert qs.process_matches(1234, "same") is False
