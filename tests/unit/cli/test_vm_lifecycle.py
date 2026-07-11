"""Unit tests for backend-aware vm_lifecycle helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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
