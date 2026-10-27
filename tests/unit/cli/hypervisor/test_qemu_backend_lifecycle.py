"""Lifecycle and failure-path tests for qemu_backend."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli.hypervisor import qemu_backend as qb
from workspace.cli.hypervisor.qemu_backend import QemuBackend
from workspace.types.vm import VMConfig


class _QmpUnavailable(qb.QmpError):
    def __init__(self) -> None:
        super().__init__("qmp unavailable")


class _ConfigFailure(RuntimeError):
    def __init__(self) -> None:
        super().__init__("config broke")


class _GuestConfigFailure(RuntimeError):
    def __init__(self) -> None:
        super().__init__("guest config broke")


def _cfg(**overrides: object) -> VMConfig:
    data: dict[str, object] = {
        "components": ["uv"],
        "isolation": {"backend": "qemu", "qemu": {"provision": "none"}},
    }
    data.update(overrides)
    return VMConfig.model_validate(data)


def _vm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **cfg: object) -> Path:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "vm.yaml").write_text(yaml.dump(_cfg(**cfg).model_dump(mode="json")))
    (vm_dir / "ssh_port").write_text("55100")
    (vm_dir / "qemu_ssh_ed25519").write_text("key")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    return vm_dir


def test_vm_mode_reads_config_and_rejects_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert qb._vm_mode(_cfg()) == "persistent"
    assert (
        qb._vm_mode(
            VMConfig.model_validate(
                {
                    "components": ["uv"],
                    "isolation": {
                        "backend": "qemu",
                        "qemu": {"provision": "none", "mode": "ephemeral"},
                    },
                }
            )
        )
        == "ephemeral"
    )
    monkeypatch.setenv(qb._MODE_ENV, "nonsense")
    with pytest.raises(ValueError, match="invalid WORKSPACE_VM_MODE"):
        qb._vm_mode(_cfg())


def test_validate_bridge_requires_name() -> None:
    cfg = _cfg(network={"mode": "bridge", "network_name": ""})
    with pytest.raises(ValueError, match="invalid qemu bridge name"):
        qb._validate_config(cfg)


def test_validate_bridge_rejects_comma() -> None:
    cfg = _cfg(network={"mode": "bridge", "network_name": "br0,br1"})
    with pytest.raises(ValueError, match="invalid qemu bridge name"):
        qb._validate_config(cfg)


def test_validate_rejects_cap_add() -> None:
    cfg = _cfg(security={"cap_add": ["NET_ADMIN"]})
    with pytest.raises(ValueError, match=r"security\.cap_add"):
        qb._validate_config(cfg)


def test_validate_rejects_api_credentials() -> None:
    cfg = _cfg(credentials={"mode": "api"})
    with pytest.raises(ValueError, match=r"credentials\.mode: api"):
        qb._validate_config(cfg)


def test_validate_mounts_relative(tmp_path: Path) -> None:
    cfg = _cfg(mounts=["relative"])
    with pytest.raises(ValueError, match="must be absolute"):
        qb._validate_config(cfg)


def test_validate_mounts_comma(tmp_path: Path) -> None:
    cfg = _cfg(mounts=[f"{tmp_path},other"])
    with pytest.raises(ValueError, match="must not contain a comma"):
        qb._validate_config(cfg)


def test_validate_mounts_missing() -> None:
    cfg = _cfg(mounts=["/definitely/missing/path"])
    with pytest.raises(FileNotFoundError, match="not found"):
        qb._validate_config(cfg)


def test_resolve_ci_root_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb, "_CI_ROOT", Path("/nonexistent/workspace-ci"))
    with pytest.raises(FileNotFoundError, match="deploy-ci"):
        qb._resolve_ci_root()


def test_pid_from_file_missing_and_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert qb._pid_from_file(tmp_path) is None
    (tmp_path / "qemu.pid").write_text("not-a-pid")
    with pytest.raises(ValueError, match="invalid QEMU PID file"):
        qb._pid_from_file(tmp_path)


def test_status_reports_metadata_and_invalid_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("4242")
    (vm_dir / "disk.qcow2").write_bytes(b"disk")
    state = MagicMock(
        mode="persistent",
        profile="guard",
        ssh_port=55100,
        last_error="boom",
        pid_start="old",
    )
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(qb, "load_state", lambda _d: state)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "process_matches", lambda *_a: False)
    status = QemuBackend().status("uuid")
    assert status["disk_bytes"] == "4"
    assert status["last_error"] == "boom"
    assert status["ssh_port"] == "55100"
    assert status["state"] == "invalid"


def test_status_invalid_pid_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    (vm_dir / "qemu.pid").write_text("oops")
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    assert QemuBackend().status("uuid")["state"] == "invalid"


def test_stop_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(tmp_path, monkeypatch)
    (vm_dir / "qemu.pid").write_text("9001")
    state = MagicMock(pid_start="old")
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "load_state", lambda _d: state)
    monkeypatch.setattr(qb, "process_matches", lambda *_a: False)
    with pytest.raises(RuntimeError, match="does not match"):
        QemuBackend().stop("uuid")


def test_stop_uses_qmp_powerdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(tmp_path, monkeypatch)
    (vm_dir / "qemu.pid").write_text("9001")
    (vm_dir / "qmp.sock").touch()
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "powerdown", lambda _p: None)
    monkeypatch.setattr(qb, "_wait_pid_exit", lambda *_a: True)
    QemuBackend().stop("uuid")
    assert not (vm_dir / "qemu.pid").exists()
    assert not (vm_dir / "qmp.sock").exists()


def test_stop_qmp_error_falls_back_to_term(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    vm_dir = _vm_dir(tmp_path, monkeypatch)
    (vm_dir / "qemu.pid").write_text("9001")
    (vm_dir / "qmp.sock").touch()
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)

    def _fail(_path: Path) -> None:
        raise _QmpUnavailable

    monkeypatch.setattr(qb, "powerdown", _fail)
    monkeypatch.setattr(qb, "_wait_pid_exit", lambda *_a: False)
    monkeypatch.setattr(qb, "_signal", lambda *_a: None)
    monkeypatch.setattr(qb, "mark_stopped", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="did not exit"):
        QemuBackend().stop("uuid")
    assert "qmp unavailable" in capsys.readouterr().err


def test_stop_reports_unexited_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(tmp_path, monkeypatch)
    (vm_dir / "qemu.pid").write_text("9001")
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "_wait_pid_exit", lambda *_a: False)
    monkeypatch.setattr(qb, "_signal", lambda *_a: None)
    with pytest.raises(RuntimeError, match="did not exit"):
        QemuBackend().stop("uuid")


def test_destroy_missing_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: None)
    QemuBackend().destroy("absent")


def test_destroy_archive_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = tmp_path / "uuid"
    vm_dir.mkdir()
    archive = tmp_path / "_archive" / "uuid"
    archive.mkdir(parents=True)
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: None)
    with pytest.raises(FileExistsError, match="archive already exists"):
        QemuBackend().destroy("uuid")


def test_signal_writes_stderr(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        MagicMock(
            side_effect=subprocess.CalledProcessError(1, "kill", stderr="denied")
        ),
    )
    qb._signal(1, "TERM")
    assert "denied" in capsys.readouterr().err


def test_process_alive_permission_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb.os, "kill", MagicMock(side_effect=PermissionError))
    assert qb._process_alive(1) is True


def test_wait_pid_exit_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qb.time, "monotonic", MagicMock(side_effect=[0, 1, 2]))
    monkeypatch.setattr(qb.time, "sleep", lambda _s: None)
    monkeypatch.setattr(qb, "_process_alive", MagicMock(side_effect=[True, False]))
    assert qb._wait_pid_exit(1, 10) is True


def test_start_reuses_live_pid_without_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(tmp_path, monkeypatch)
    (vm_dir / "qemu.pid").write_text("9001")
    monkeypatch.setattr(QemuBackend, "status", lambda self, _uuid: {"state": "stopped"})
    monkeypatch.setattr(qb, "_pid_from_file", lambda _d: 9001)
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    QemuBackend().start("uuid")


def test_start_rejects_stale_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(tmp_path, monkeypatch)
    (vm_dir / "qemu.pid").write_text("9001")
    qb.mark_started(vm_dir, ssh_port=55100, pid_start="old")
    monkeypatch.setattr(QemuBackend, "status", lambda self, _uuid: {"state": "stopped"})
    monkeypatch.setattr(qb, "_process_alive", lambda _pid: True)
    monkeypatch.setattr(qb, "process_matches", lambda *_a: False)
    with pytest.raises(RuntimeError, match="stale QEMU PID"):
        QemuBackend().start("uuid")


def test_start_launch_failure_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vm_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(QemuBackend, "status", lambda self, _uuid: {"state": "stopped"})
    monkeypatch.setattr(qb, "_pid_from_file", lambda _d: None)
    monkeypatch.setattr(qb, "resolve_qemu_system", lambda _a: Path("/opt/qemu"))
    monkeypatch.setattr(qb, "resolve_accel", lambda *_a: "tcg")
    monkeypatch.setattr(qb, "resolve_aarch64_firmware", lambda: None)
    monkeypatch.setattr(qb, "build_qemu_argv", lambda **_k: ["/opt/qemu"])
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(2, "qemu")),
    )
    with pytest.raises(subprocess.CalledProcessError):
        QemuBackend().start("uuid")


def test_start_applies_host_shares_when_provisioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(
        tmp_path,
        monkeypatch,
        isolation={"backend": "qemu", "qemu": {"provision": "guard"}},
    )
    calls: list[str] = []
    monkeypatch.setattr(QemuBackend, "status", lambda self, _uuid: {"state": "stopped"})
    monkeypatch.setattr(qb, "_pid_from_file", lambda _d: None)
    monkeypatch.setattr(qb, "resolve_qemu_system", lambda _a: Path("/opt/qemu"))
    monkeypatch.setattr(qb, "resolve_accel", lambda *_a: "tcg")
    monkeypatch.setattr(qb, "resolve_aarch64_firmware", lambda: None)
    monkeypatch.setattr(qb, "build_qemu_argv", lambda **_k: ["/opt/qemu"])
    monkeypatch.setattr(qb, "find_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(qb, "_resolve_ci_root", lambda: tmp_path)
    monkeypatch.setattr(
        qb, "apply_host_shares", lambda *_a, **_k: calls.append("shares")
    )
    monkeypatch.setattr(qb, "apply_mounts", lambda *_a, **_k: calls.append("mounts"))
    monkeypatch.setattr(qb, "_wait_ssh", lambda *_a, **_k: None)
    monkeypatch.setattr(
        qb.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess("qemu", 0)
    )
    QemuBackend().start("uuid")
    assert calls == ["shares", "mounts"]
    assert vm_dir.is_dir()


def test_rebuild_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match=r"vm\.yaml"):
        QemuBackend().rebuild("absent")


def test_rebuild_restarts_and_reconfigures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vm_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: None)
    monkeypatch.setattr(QemuBackend, "start", lambda self, _uuid, **_k: None)
    monkeypatch.setattr(qb, "apply_guest_config", lambda *_a, **_k: None)
    QemuBackend().rebuild("uuid")


def test_rebuild_fresh_replaces_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vm_dir = _vm_dir(
        tmp_path,
        monkeypatch,
        isolation={"backend": "qemu", "qemu": {"provision": "guard"}},
    )
    (vm_dir / "disk.qcow2").write_bytes(b"old")
    calls: list[str] = []
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: calls.append("stop"))
    monkeypatch.setattr(
        QemuBackend, "start", lambda self, _uuid, **_k: calls.append("start")
    )
    monkeypatch.setattr(qb, "_resolve_ci_root", lambda: tmp_path)
    monkeypatch.setattr(qb, "prepare_vm_storage", lambda *_a, **_k: "55100")
    monkeypatch.setattr(qb, "provision_guest", lambda **_k: calls.append("provision"))
    monkeypatch.setattr(qb, "apply_guest_config", lambda *_a, **_k: None)
    QemuBackend().rebuild("uuid", fresh=True)
    assert (vm_dir / "backups").is_dir()
    assert calls == ["stop", "start", "provision", "stop", "start"]


def test_rebuild_failure_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vm_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(QemuBackend, "stop", lambda self, _uuid: None)
    monkeypatch.setattr(QemuBackend, "start", lambda self, _uuid, **_k: None)

    def _fail(*_a: object, **_k: object) -> None:
        raise _ConfigFailure

    monkeypatch.setattr(qb, "apply_guest_config", _fail)
    with pytest.raises(_ConfigFailure, match="config broke"):
        QemuBackend().rebuild("uuid")


def test_create_launch_failure_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "vm.yaml"
    config.write_text(yaml.dump(_cfg().model_dump(mode="json")))
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path / "vms")
    monkeypatch.setattr(qb, "uuid7", lambda: "uuid")
    monkeypatch.setattr(qb, "_generate_password", lambda: "secret")
    monkeypatch.setattr(qb, "resolve_qemu_system", lambda _a: Path("/opt/qemu"))
    monkeypatch.setattr(qb, "resolve_accel", lambda *_a: "tcg")
    monkeypatch.setattr(qb, "resolve_aarch64_firmware", lambda: None)
    monkeypatch.setattr(qb, "prepare_vm_storage", lambda *_a, **_k: "55100")
    monkeypatch.setattr(qb, "build_qemu_argv", lambda **_k: ["/opt/qemu"])
    monkeypatch.setattr(
        qb.subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(2, "qemu")),
    )
    with pytest.raises(subprocess.CalledProcessError):
        QemuBackend().create(str(config), _cfg())


def test_create_guest_config_failure_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "vm.yaml"
    config.write_text(yaml.dump(_cfg().model_dump(mode="json")))
    monkeypatch.setattr(qb, "_VMS_DIR", tmp_path / "vms")
    monkeypatch.setattr(qb, "uuid7", lambda: "uuid")
    monkeypatch.setattr(qb, "_generate_password", lambda: "secret")
    monkeypatch.setattr(qb, "resolve_qemu_system", lambda _a: Path("/opt/qemu"))
    monkeypatch.setattr(qb, "resolve_accel", lambda *_a: "tcg")
    monkeypatch.setattr(qb, "resolve_aarch64_firmware", lambda: None)
    monkeypatch.setattr(qb, "prepare_vm_storage", lambda *_a, **_k: "55100")
    monkeypatch.setattr(qb, "build_qemu_argv", lambda **_k: ["/opt/qemu"])
    monkeypatch.setattr(
        qb.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess("qemu", 0)
    )
    monkeypatch.setattr(qb, "_wait_ssh", lambda *_a, **_k: None)

    def _fail(*_a: object, **_k: object) -> None:
        raise _GuestConfigFailure

    monkeypatch.setattr(qb, "apply_guest_config", _fail)
    with pytest.raises(_GuestConfigFailure, match="guest config broke"):
        QemuBackend().create(str(config), _cfg())
