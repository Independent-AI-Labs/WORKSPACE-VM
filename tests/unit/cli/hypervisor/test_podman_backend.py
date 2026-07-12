"""Unit tests for podman_backend."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from workspace.cli.hypervisor import podman_backend as pb
from workspace.cli.hypervisor.podman_backend import PodmanBackend


def test_remove_volume_swallows_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    err = subprocess.CalledProcessError(1, "podman", stderr="busy")

    def _raise(*_a: object, **_k: object) -> None:
        raise err

    writes: list[str] = []
    monkeypatch.setattr(pb.subprocess, "run", _raise)
    monkeypatch.setattr(pb.sys.stderr, "write", writes.append)
    pb._remove_volume("vol-name")
    assert writes == ["busy"]


def test_purge_volumes_calls_remove(monkeypatch: pytest.MonkeyPatch) -> None:
    removed: list[str] = []
    monkeypatch.setattr(pb, "_remove_volume", removed.append)
    pb._purge_volumes("uuid-1")
    assert removed == [
        "uuid-1-workspace",
        "uuid-1-transcripts",
        "uuid-1-cache",
    ]


def test_ssh_endpoint_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="podman backend"):
        PodmanBackend().ssh_endpoint("uuid")


def test_destroy_running_purges_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = PodmanBackend()
    monkeypatch.setattr(backend, "status", lambda _uuid: {"state": "running"})
    podman_calls: list[tuple[str, ...]] = []

    def _fake_podman(*args: str) -> MagicMock:
        podman_calls.append(args)
        result = MagicMock()
        result.stdout = ""
        return result

    monkeypatch.setattr(pb, "_podman", _fake_podman)
    monkeypatch.setattr(
        pb.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess("podman", 0, "", ""),
    )
    monkeypatch.setattr(pb, "_remove_hosts_entry", lambda _uuid: None)
    purged: list[str] = []
    monkeypatch.setattr(pb, "_purge_volumes", purged.append)

    backend.destroy("uuid-1", purge=True)
    assert ("rm", "-f", "uuid-1") in podman_calls
    assert purged == ["uuid-1"]
