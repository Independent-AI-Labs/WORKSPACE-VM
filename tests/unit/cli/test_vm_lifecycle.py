"""Unit tests for backend-aware vm_lifecycle helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from workspace.cli import vm_lifecycle
from workspace.cli.vm_main import main


def _patch_vms_dir(monkeypatch, tmp_path: Path) -> Path:
    vms_dir = tmp_path / ".vms"
    vms_dir.mkdir()
    monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", vms_dir)
    return vms_dir


class TestListVms:
    def test_lists_qemu_and_podman_backends(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        qemu_dir = vms_dir / "qemu-uuid"
        qemu_dir.mkdir()
        (qemu_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["opencode"], "isolation": {"backend": "qemu"}})
        )
        (qemu_dir / "qemu.pid").write_text("99999")

        podman_dir = vms_dir / "podman-uuid"
        podman_dir.mkdir()
        (podman_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["opencode"], "isolation": {"backend": "podman"}})
        )

        mock_podman = MagicMock()
        mock_podman.return_value.stdout = "false"
        monkeypatch.setattr("workspace.cli.vm_core._podman", mock_podman)

        def fake_kill(args, **kwargs):
            result = MagicMock()
            result.returncode = 1 if args[-1] == "99999" else 0
            return result

        monkeypatch.setattr(vm_lifecycle.subprocess, "run", fake_kill)

        main(["list"])
        output = capsys.readouterr().out
        assert "qemu-uuid" in output
        assert "podman-uuid" in output
        assert "qemu" in output
        assert "podman" in output


class TestVMMainLifecycle:
    def test_start_missing_uuid(self) -> None:
        assert main(["start"]) == 1

    def test_delete_parses_purge_flag(self, tmp_path: Path, monkeypatch) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "del-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["opencode"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        monkeypatch.setattr(
            "workspace.cli.vm_lifecycle.get_backend", lambda _cfg: backend
        )

        assert main(["delete", "del-uuid", "--purge"]) == 0
        backend.destroy.assert_called_once_with("del-uuid", purge=True)


class TestQemuLifecycle:
    def test_start_already_running(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        backend.status.return_value = {"state": "running"}
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)

        vm_lifecycle.start("qemu-uuid")
        assert "already running" in capsys.readouterr().out
        backend.start.assert_not_called()

    def test_start_qemu_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        backend.status.return_value = {"state": "stopped"}
        monkeypatch.setattr(
            vm_lifecycle,
            "backend_for_uuid",
            lambda _uuid: backend,
        )

        vm_lifecycle.start("qemu-uuid")
        backend.start.assert_called_once_with("qemu-uuid")
        assert "started" in capsys.readouterr().out

    def test_stop_qemu_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )
        (vm_dir / "pid").write_text("1")

        backend = MagicMock()
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)

        vm_lifecycle.stop("qemu-uuid")
        backend.stop.assert_called_once_with("qemu-uuid")
        assert not (vm_dir / "pid").exists()

    def test_shell_qemu_execvp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )
        (vm_dir / "ssh_port").write_text("55100")
        (vm_dir / "qemu_ssh_ed25519").write_text("key")

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        backend.status.return_value = {"state": "running"}
        backend.ssh_endpoint.return_value = ("127.0.0.1", 55100)
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)
        invoked: list[str] = []

        def _execvp(bin_name: str, _args: list[str]) -> None:
            invoked.append(bin_name)
            raise SystemExit(0)

        monkeypatch.setattr(vm_lifecycle.os, "execvp", _execvp)

        with pytest.raises(SystemExit):
            vm_lifecycle.shell("qemu-uuid")
        assert invoked == ["ssh"]

    def test_shell_not_running_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        backend.status.return_value = {"state": "stopped"}
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)
        monkeypatch.setattr(
            vm_lifecycle.sys,
            "exit",
            lambda code: (_ for _ in ()).throw(SystemExit(code)),
        )

        with pytest.raises(SystemExit) as exc:
            vm_lifecycle.shell("qemu-uuid")
        assert exc.value.code == 1

    def test_exec_cmd_qemu(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        backend.status.return_value = {"state": "running"}
        backend.exec.return_value = MagicMock(stdout="hello\n", stderr="")
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)

        vm_lifecycle.exec_cmd("qemu-uuid", ["echo", "hello"])
        assert "hello" in capsys.readouterr().out

    def test_show_status_qemu_with_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )
        (vm_dir / "qemu.log").write_text("boot")

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        backend.status.return_value = {
            "state": "running",
            "backend": "qemu",
            "pid": "1",
        }
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)

        vm_lifecycle.show_status("qemu-uuid")
        assert "qemu.log" in capsys.readouterr().out

    def test_kill_qemu(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )
        (vm_dir / "qemu.pid").write_text("4242")

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)
        monkeypatch.setattr(
            vm_lifecycle.subprocess,
            "run",
            lambda *_a, **_k: MagicMock(returncode=0),
        )

        vm_lifecycle.kill("qemu-uuid")
        assert "killed" in capsys.readouterr().out

    def test_delete_without_purge_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)

        vm_lifecycle.delete("qemu-uuid", purge=False)
        output = capsys.readouterr().out
        assert "deleted" in output
        assert "purged" not in output

    def test_show_logs_missing_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)
        monkeypatch.setattr(
            vm_lifecycle.sys,
            "exit",
            lambda code: (_ for _ in ()).throw(SystemExit(code)),
        )

        with pytest.raises(SystemExit) as exc:
            vm_lifecycle.show_logs("qemu-uuid", [])
        assert exc.value.code == 1

    def test_kill_qemu_missing_pid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)
        monkeypatch.setattr(
            vm_lifecycle.sys,
            "exit",
            lambda code: (_ for _ in ()).throw(SystemExit(code)),
        )

        with pytest.raises(SystemExit) as exc:
            vm_lifecycle.kill("qemu-uuid")
        assert exc.value.code == 1

    def test_show_logs_qemu_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "qemu-uuid"
        vm_dir.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "isolation": {"backend": "qemu"}})
        )
        (vm_dir / "qemu.log").write_text("line1\n")

        backend = MagicMock()
        backend.backend_name.return_value = "qemu"
        monkeypatch.setattr(vm_lifecycle, "backend_for_uuid", lambda _uuid: backend)
        monkeypatch.setattr(
            vm_lifecycle.subprocess,
            "run",
            lambda *_a, **_k: MagicMock(returncode=0),
        )

        vm_lifecycle.show_logs("qemu-uuid", ["--tail", "5"])

    def test_load_vm_config_missing_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_vms_dir(monkeypatch, tmp_path)
        monkeypatch.setattr(
            vm_lifecycle.sys,
            "exit",
            lambda code: (_ for _ in ()).throw(SystemExit(code)),
        )
        with pytest.raises(SystemExit) as exc:
            vm_lifecycle.load_vm_config("missing")
        assert exc.value.code == 1

    def test_list_vms_empty_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", tmp_path / "missing")
        vm_lifecycle.list_vms()
        assert "No VMs found" in capsys.readouterr().out
