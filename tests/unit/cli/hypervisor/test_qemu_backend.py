"""Unit tests for qemu_backend."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli.hypervisor import qemu_backend as qb
from workspace.cli.hypervisor.qemu_backend import QemuBackend
from workspace.types.vm import VMConfig


def test_backend_name() -> None:
    assert QemuBackend().backend_name() == "qemu"


def test_status_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    assert QemuBackend().status("missing") == {"state": "unknown", "backend": "qemu"}


def test_status_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("4242")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    assert QemuBackend().status("uuid") == {
        "state": "running",
        "backend": "qemu",
        "pid": "4242",
    }


def test_status_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("4242")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: False)
    assert QemuBackend().status("uuid") == {"state": "stopped", "backend": "qemu"}


def test_exec_runs_ssh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "ssh_port").write_text("55123")
    (vm_dir / "qemu_ssh_ed25519").write_text("key")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess("ssh", 0, "out", ""),
    )
    result = QemuBackend().exec("uuid", ["uname", "-a"])
    assert result.stdout == "out"


def test_ssh_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "ssh_port").write_text("55123")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    assert QemuBackend().ssh_endpoint("uuid") == ("127.0.0.1", 55123)


def test_stop_without_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    QemuBackend().stop("uuid")


def test_stop_escalates_to_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("9001")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "_wait_pid_exit", MagicMock(side_effect=[False, True]))
    calls: list[list[str]] = []

    def _fake_run(
        cmd: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(qb.subprocess, "run", _fake_run)
    QemuBackend().stop("uuid")
    assert calls[0][:2] == ["kill", "-TERM"]
    assert calls[-1][:2] == ["kill", "-KILL"]


def test_stop_sends_term(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("9001")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "_wait_pid_exit", lambda *_a, **_k: True)
    calls: list[list[str]] = []

    def _fake_run(
        cmd: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(qb.subprocess, "run", _fake_run)
    QemuBackend().stop("uuid")
    assert calls[0][:2] == ["kill", "-TERM"]
    assert not (vm_dir / "qemu.pid").exists()


def test_stop_dead_pid_clears_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("9001")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: False)
    QemuBackend().stop("uuid")
    assert not (vm_dir / "qemu.pid").exists()


def test_destroy_purges_vm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "marker").write_text("x")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: None)
    QemuBackend().destroy("uuid", purge=True)
    assert not vm_dir.exists()


def test_destroy_archives_vm_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "marker").write_text("x")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: None)
    QemuBackend().destroy("uuid")
    assert not vm_dir.exists()
    assert (tmp_path / "_archive" / "uuid" / "marker").is_file()


def test_process_alive_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb.os, "kill", MagicMock(return_value=None))
    assert qb._process_alive(1) is True


def test_process_alive_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb.os, "kill", MagicMock(side_effect=ProcessLookupError))
    assert qb._process_alive(1) is False


def test_probe_ssh_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess("ssh", 0, "ok", ""),
    )
    assert qb._probe_ssh(55000, Path("/tmp/key")) is True


def test_probe_ssh_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(255, "ssh")),
    )
    assert qb._probe_ssh(55000, Path("/tmp/key")) is False


def test_wait_ssh_returns_when_probe_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb, "_probe_ssh", lambda *_a, **_k: True)
    qb._wait_ssh(55000, Path("/tmp/key"))


def test_wait_ssh_timeout_warns(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    monkeypatch.setattr(qb, "_probe_ssh", lambda *_a, **_k: False)
    monkeypatch.setattr(qb.time, "monotonic", MagicMock(side_effect=[0, 200]))
    monkeypatch.setattr(qb.time, "sleep", lambda _s: None)
    qb._wait_ssh(55000, Path("/tmp/key"))
    assert "timed out" in capsys.readouterr().err


def test_start_missing_vm_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match=r"vm\.yaml"):
        QemuBackend().start("uuid")


def test_create_boots_and_provisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vms = tmp_path / ".vms"
    vms.mkdir()
    config = tmp_path / "vm-poc.yaml"
    config.write_text(
        yaml.dump(
            {
                "components": ["uv"],
                "web_ui": False,
                "isolation": {
                    "backend": "qemu",
                    "qemu": {"guest_arch": "aarch64", "provision": "guard"},
                },
            }
        )
    )
    monkeypatch.setattr(qb, "_VMS_DIR", vms)
    monkeypatch.setattr(qb, "uuid7", lambda: "00000000-0000-7000-8000-000000000001")
    monkeypatch.setattr(qb, "_generate_password", lambda: "secret")
    monkeypatch.setattr(qb, "resolve_qemu_system", lambda _arch: Path("/opt/qemu"))
    monkeypatch.setattr(qb, "resolve_accel", lambda _req, _bin: "tcg")
    monkeypatch.setattr(qb, "resolve_aarch64_firmware", lambda: Path("/opt/efi.fd"))
    monkeypatch.setattr(qb, "_resolve_ci_root", lambda: tmp_path / "workspace-ci")

    def _prepare(_cfg: object, vm_dir: Path, **_kwargs: object) -> str:
        (vm_dir / "ssh_port").write_text("55010")
        return "55010"

    monkeypatch.setattr(qb, "prepare_vm_storage", _prepare)
    monkeypatch.setattr(
        qb, "build_qemu_argv", lambda **_k: ["/opt/qemu", "-display", "none"]
    )
    monkeypatch.setattr(qb, "_wait_ssh", lambda *_a, **_k: None)
    monkeypatch.setattr(qb, "provision_guest", lambda **_k: None)
    monkeypatch.setattr(qb, "apply_guest_config", lambda *_a, **_k: None)
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess("qemu", 0, "", ""),
    )

    QemuBackend().create(
        str(config), VMConfig.model_validate(yaml.safe_load(config.read_text()))
    )

    vm_dir = vms / "00000000-0000-7000-8000-000000000001"
    assert vm_dir.is_dir()
    assert (vm_dir / "vm.yaml").is_file()


def test_start_launches_qemu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    cfg = {
        "components": ["uv"],
        "web_ui": False,
        "isolation": {
            "backend": "qemu",
            "qemu": {"guest_arch": "aarch64", "provision": "none"},
        },
    }
    (vm_dir / "vm.yaml").write_text(yaml.dump(cfg))
    (vm_dir / "ssh_port").write_text("55100")
    (vm_dir / "qemu_ssh_ed25519").write_text("key")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "resolve_qemu_system", lambda _arch: Path("/opt/qemu"))
    monkeypatch.setattr(qb, "resolve_accel", lambda _req, _bin: "tcg")
    monkeypatch.setattr(qb, "resolve_aarch64_firmware", lambda: None)
    monkeypatch.setattr(qb, "build_qemu_argv", lambda **_k: ["/opt/qemu"])
    monkeypatch.setattr(qb, "_wait_ssh", lambda *_a, **_k: None)
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess("qemu", 0, "", ""),
    )

    QemuBackend().start("uuid")


def test_start_already_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    cfg = {
        "components": ["uv"],
        "web_ui": False,
        "isolation": {"backend": "qemu", "qemu": {"guest_arch": "aarch64"}},
    }
    (vm_dir / "vm.yaml").write_text(yaml.dump(cfg))
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(
        QemuBackend,
        "status",
        lambda self, _uuid: {"state": "running"},
    )
    QemuBackend().start("uuid")


def test_validate_config_rejects_host_network() -> None:
    cfg = VMConfig.model_validate(
        {
            "components": ["uv"],
            "network": {"mode": "host"},
            "isolation": {"backend": "qemu"},
        }
    )
    with pytest.raises(ValueError, match=r"network\.mode: host"):
        qb._validate_config(cfg)


def test_validate_config_rejects_openvpn_netns() -> None:
    cfg = VMConfig.model_validate(
        {
            "components": ["uv"],
            "network": {
                "mode": "openvpn",
                "vpn_type": "netns",
                "vpn_netns": "vpn0",
            },
            "isolation": {"backend": "qemu"},
        }
    )
    with pytest.raises(ValueError, match=r"vpn_type: netns"):
        qb._validate_config(cfg)


def test_validate_config_rejects_whitelist() -> None:
    cfg = VMConfig.model_validate(
        {
            "components": ["uv"],
            "network": {
                "mode": "bridge",
                "network_name": "br0",
                "whitelist": ["example.com"],
            },
            "isolation": {"backend": "qemu"},
        }
    )
    with pytest.raises(ValueError, match=r"network\.whitelist"):
        qb._validate_config(cfg)
