"""Unit tests for qemu_provision."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workspace.cli.hypervisor import qemu_provision as qp
from workspace.types.vm import VMConfig

_MIN_SSH_CALLS = 2


def _cfg(profile: str) -> VMConfig:
    return VMConfig.model_validate(
        {
            "components": ["uv"],
            "isolation": {
                "backend": "qemu",
                "qemu": {"guest_arch": "aarch64", "provision": profile},
            },
        }
    )


def test_provision_guest_runs_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _fake_ssh(
        _ssh: qp._SshSession,
        script: str,
        *,
        timeout: int,
        log,
        raise_on_error: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(script[:40])
        return subprocess.CompletedProcess("ssh", 0, "ok", "")

    monkeypatch.setattr(qp, "_wait_ro_mount", lambda *_a, **_k: None)
    monkeypatch.setattr(qp, "_ssh_run", _fake_ssh)
    monkeypatch.setattr(qp, "_scp_file", lambda *_a, **_k: None)
    monkeypatch.setattr(qp.os.environ, "get", lambda key, default=None: default)

    qp.provision_guest(
        cfg=_cfg("guard"),
        vm_dir=tmp_path,
        ssh_port=55000,
        ssh_key=tmp_path / "key",
        install_defaults=tmp_path / "defaults.yaml",
    )
    assert len(calls) >= _MIN_SSH_CALLS
    assert (tmp_path / "provision.log").is_file()


def test_provision_guest_none_is_noop(tmp_path: Path) -> None:
    qp.provision_guest(
        cfg=_cfg("none"),
        vm_dir=tmp_path,
        ssh_port=55000,
        ssh_key=tmp_path / "key",
        install_defaults=tmp_path / "defaults.yaml",
    )


def test_build_rsync_script_guard_profile() -> None:
    script = qp._build_rsync_script("guard")
    assert "projects/WORKSPACE-GUARD/" in script
    assert "projects/CI/" in script
    assert "rsync -a" in script
    assert "mkdir -p /opt/workspace/projects" in script
    assert "chown -R workspace:workspace /opt/workspace" in script


def test_build_rsync_script_full_ci_profile() -> None:
    script = qp._build_rsync_script("full-ci")
    assert "projects/" in script


def test_build_install_script_guard_skips_install_ci() -> None:
    script = qp._build_install_script("guard", [])
    assert "make init" in script
    assert "install-ci" not in script


def test_build_install_script_full_ci_runs_install_ci() -> None:
    script = qp._build_install_script("full-ci", [])
    assert "make install-ci" in script


def test_wait_ro_mount_success(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh = qp._SshSession(55000, Path("/tmp/key"))
    responses = [
        subprocess.CompletedProcess("ssh", 1, "", ""),
        subprocess.CompletedProcess("ssh", 0, "ok", ""),
    ]

    def _fake_ssh(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return responses.pop(0)

    logs: list[str] = []
    monkeypatch.setattr(qp, "_ssh_run", _fake_ssh)
    qp._wait_ro_mount(ssh, timeout=10, log=logs.append)
    assert any("ready" in line for line in logs)


def test_wait_ro_mount_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh = qp._SshSession(55000, Path("/tmp/key"))
    monkeypatch.setattr(
        qp,
        "_ssh_run",
        lambda *_a, **_k: subprocess.CompletedProcess("ssh", 1, "", ""),
    )
    monkeypatch.setattr(qp.time, "monotonic", MagicMock(side_effect=[0, 0, 200]))
    with pytest.raises(TimeoutError, match="timed out"):
        qp._wait_ro_mount(ssh, timeout=1, log=lambda _m: None)


def test_ssh_run_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ssh = qp._SshSession(55000, Path("/tmp/key"))
    monkeypatch.setattr(
        qp.proc,
        "run_result",
        lambda *_a, **_k: subprocess.CompletedProcess("ssh", 2, "", "fail"),
    )
    with pytest.raises(subprocess.CalledProcessError):
        qp._ssh_run(ssh, "false", timeout=5, log=lambda _m: None)
