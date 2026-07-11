"""Unit tests for vm_manager helper functions (no podman required)."""

from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml as _yaml

from workspace.cli.vm_build import (
    _build_run_args,
    _derive_cap_flags,
    _derive_network_flags,
    _get_uid,
    _pre_copy_files,
)
from workspace.cli.vm_core import (
    _config_sha256,
    _generate_dockerignore,
    _generate_password,
    _podman,
    _remove_hosts_entry,
    _render_template,
)
from workspace.cli.vm_main import main
from workspace.cli.vm_manager import create, rebuild
from workspace.cli.vm_sync import sync
from workspace.types.vm import VMConfig

_PASSWORD_LEN = 32
_UNIQUENESS_COUNT = 100
_SHA256_HEX_LEN = 16


class TestGeneratePassword:
    def test_length(self) -> None:
        pw = _generate_password(_PASSWORD_LEN)
        assert len(pw) == _PASSWORD_LEN

    def test_alphanumeric(self) -> None:
        pw = _generate_password(64)
        assert pw.isalnum()

    def test_uniqueness(self) -> None:
        passwords = {
            _generate_password(_PASSWORD_LEN) for _ in range(_UNIQUENESS_COUNT)
        }
        assert len(passwords) == _UNIQUENESS_COUNT


class TestConfigSha256:
    def test_stable(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        digest = _config_sha256(cfg)
        assert len(digest) == _SHA256_HEX_LEN
        assert digest == _config_sha256(cfg)

    def test_different_configs(self) -> None:
        a = VMConfig.model_validate({"components": ["opencode"]})
        b = VMConfig.model_validate({"components": ["opencode", "traefik"]})
        assert _config_sha256(a) != _config_sha256(b)


class TestRenderTemplate:
    def test_renders_opencode_service(self) -> None:
        result = _render_template(
            "systemd-opencode.service.j2",
            {"password": "pw", "traefik_enabled": False, "network_enabled": False},
        )
        assert "OPENCODE_SERVER_PASSWORD=pw" in result


class TestDeriveNetworkFlags:
    def test_none_mode(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        flags = _derive_network_flags(cfg)
        assert flags == ["--network", "none"]

    def test_bridge_mode(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["opencode"], "network": {"mode": "bridge"}}
        )
        flags = _derive_network_flags(cfg)
        assert "--network" in flags
        assert "workspace-vm-net" in flags

    def test_host_mode(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["opencode"], "network": {"mode": "host"}}
        )
        flags = _derive_network_flags(cfg)
        assert flags == ["--network", "host"]

    def test_openvpn_netns(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {
                    "mode": "openvpn",
                    "vpn_type": "netns",
                    "vpn_netns": "myvpn",
                    "vpn_config": "/tmp/client.ovpn",
                },
            }
        )
        flags = _derive_network_flags(cfg)
        assert "--network" in flags
        assert "ns:/run/netns/myvpn" in flags


class TestDeriveCapFlags:
    def test_default_no_caps(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        flags = _derive_cap_flags(cfg)
        assert "--cap-drop" in flags
        assert "ALL" in flags
        assert "--cap-add" not in flags

    def test_internet_policy_adds_net_admin(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {"mode": "bridge", "policy": "internet"},
            }
        )
        flags = _derive_cap_flags(cfg)
        assert "--cap-add" in flags
        assert "NET_ADMIN" in flags

    def test_user_override(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "security": {"cap_add": ["SYS_PTRACE"]},
            }
        )
        flags = _derive_cap_flags(cfg)
        assert "SYS_PTRACE" in flags
        assert "NET_ADMIN" not in flags

    def test_openvpn_container_adds_net_admin(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {
                    "mode": "openvpn",
                    "vpn_type": "container",
                    "vpn_config": "/tmp/test.ovpn",
                },
            }
        )
        flags = _derive_cap_flags(cfg)
        assert "NET_ADMIN" in flags

    def test_unrestricted_no_extra_caps(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {"mode": "bridge", "policy": "unrestricted"},
            }
        )
        flags = _derive_cap_flags(cfg)
        assert "NET_ADMIN" not in flags
        assert "--cap-add" not in flags


class TestCLIDispatch:
    def test_help_flag(self) -> None:
        result = subprocess.run(
            ["bash", "workspace/scripts/bin/vm", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout

    def test_dash_h_flag(self) -> None:
        result = subprocess.run(
            ["bash", "workspace/scripts/bin/vm", "-h"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout

    def test_no_args_shows_usage(self) -> None:
        result = subprocess.run(
            ["bash", "workspace/scripts/bin/vm"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout

    def test_unknown_subcommand(self) -> None:
        result = subprocess.run(
            ["bash", "workspace/scripts/bin/vm", "nonexistent"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 1
        assert "unknown subcommand" in result.stderr


class TestPodman:
    @pytest.mark.skipif(
        subprocess.run(
            ["podman", "version"], capture_output=True, text=True, check=False
        ).returncode
        != 0,
        reason="podman socket not running",
    )
    def test_podman_wrapper(self) -> None:
        result = _podman("version")
        assert result.returncode == 0
        assert "Version:" in result.stdout


class TestGetUid:
    def test_returns_digit_string(self) -> None:
        uid = _get_uid()
        assert uid.isdigit()
        assert len(uid) > 0


class TestGenerateDockerignore:
    def test_writes_dockerignore(self, tmp_path: Path) -> None:
        vm_dir = tmp_path / "test-vm"
        vm_dir.mkdir()
        _generate_dockerignore(vm_dir)
        di = vm_dir / ".dockerignore"
        assert di.exists()
        content = di.read_text()
        assert "password" in content
        assert "pid" in content
        assert "vm.yaml" in content


class TestBuildRunArgs:
    def test_minimal_config_args(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        args = _build_run_args(cfg, "test-uuid")
        assert "podman" in args[0]
        assert "run" in args
        assert "-d" in args
        assert "test-uuid" in args
        assert "workspace.type=vm" in args
        assert "workspace.uuid=test-uuid" in args
        assert "workspace.config=" in " ".join(args)
        assert "--network" in args
        assert "none" in args
        assert "--userns=keep-id" in args
        assert "--memory" in args
        assert "4g" in args
        assert "--cpus" in args
        assert "--pids-limit" in args
        assert "--health-on-failure=stop" in args

    def test_read_only_args(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        args = _build_run_args(cfg, "test-uuid")
        assert "--read-only" in args
        assert "--tmpfs" in args
        assert "/tmp:rw,noexec,nosuid" in args
        assert "/run:rw,noexec,nosuid" in args

    def test_no_new_privileges(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        args = _build_run_args(cfg, "test-uuid")
        assert "--security-opt" in args
        assert "no-new-privileges" in args

    def test_env_vars_injected(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["opencode"], "env": {"KEY": "val"}}
        )
        args = _build_run_args(cfg, "test-uuid")
        assert "-e" in args
        assert "KEY=val" in args

    def test_bridge_network_mode(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["opencode"], "network": {"mode": "bridge"}}
        )
        args = _build_run_args(cfg, "test-uuid")
        assert "--network" in args
        assert "workspace-vm-net" in args

    def test_permissive_security_skips_flags(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "security": {"no_new_privileges": False, "read_only_rootfs": False},
            }
        )
        args = _build_run_args(cfg, "test-uuid")
        assert "no-new-privileges" not in args
        assert "--read-only" not in args


class TestRemoveHostsEntry:
    def test_no_file_no_error(self, tmp_path: Path) -> None:
        _remove_hosts_entry("nonexistent-uuid-12345")


class TestVMMainDispatch:
    """In-process tests for vm_main.main()."""

    def test_no_args(self) -> None:
        assert main([]) == 1

    def test_create_missing_args(self) -> None:
        assert main(["create"]) == 1

    def test_rebuild_missing_args(self) -> None:
        assert main(["rebuild"]) == 1

    def test_sync_missing_args(self) -> None:
        assert main(["sync"]) == 1

    def test_unknown_subcommand(self) -> None:
        assert main(["nonexistent"]) == 1

    def test_create_with_config(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr("workspace.cli.vm_core._podman", _fake_podman_run)
        monkeypatch.setattr(
            "workspace.cli.vm_manager._ensure_podman_machine", lambda: None
        )
        monkeypatch.setattr("workspace.cli.vm_build._get_uid", lambda: "1000")
        _patch_vms_dir(monkeypatch, tmp_path)
        cfg = tmp_path / "test.yaml"
        cfg.write_text("components: [opencode]")

        rc = main(["create", str(cfg)])
        assert rc == 0

    def test_rebuild_with_uuid(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr("workspace.cli.vm_core._podman", _fake_podman_run)
        monkeypatch.setattr(
            "workspace.cli.vm_manager._ensure_podman_machine", lambda: None
        )
        monkeypatch.setattr("workspace.cli.vm_build._get_uid", lambda: "1000")
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "test-uuid"
        vm_dir.mkdir(parents=True, exist_ok=True)
        (vm_dir / "vm.yaml").write_text("components: [opencode]")
        (vm_dir / "password").write_text("a" * 32)
        (vm_dir / "certs").mkdir(exist_ok=True)

        rc = main(["rebuild", "test-uuid"])
        assert rc == 0

    def test_sync_with_uuid(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr("workspace.cli.vm_manager._podman", _fake_podman_run)
        monkeypatch.setattr("workspace.cli.vm_core._podman", _fake_podman_run)
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        monkeypatch.setattr("workspace.cli.vm_core._VMS_DIR", vms_dir)
        vm_dir = vms_dir / "test-sync"
        vm_dir.mkdir(parents=True, exist_ok=True)
        (vm_dir / "vm.yaml").write_text(
            _yaml.dump({"components": ["opencode"], "sync": [{"dir": str(tmp_path)}]})
        )

        rc = main(["sync", "test-sync"])
        assert rc == 0


class TestVMManagerCreate:
    def test_create_monkeypatched(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr("workspace.cli.vm_core._podman", _fake_podman_run)
        monkeypatch.setattr(
            "workspace.cli.vm_manager._ensure_podman_machine", lambda: None
        )
        monkeypatch.setattr("workspace.cli.vm_build._get_uid", lambda: "1000")
        _patch_vms_dir(monkeypatch, tmp_path)
        cfg = tmp_path / "test.yaml"
        cfg.write_text("components: [opencode]")

        create(str(cfg))


class TestVMManagerRebuild:
    def test_rebuild_monkeypatched(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr("workspace.cli.vm_core._podman", _fake_podman_run)
        monkeypatch.setattr(
            "workspace.cli.vm_manager._ensure_podman_machine", lambda: None
        )
        monkeypatch.setattr("workspace.cli.vm_build._get_uid", lambda: "1000")
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        vm_dir = vms_dir / "test-uuid"
        vm_dir.mkdir(parents=True, exist_ok=True)
        (vm_dir / "vm.yaml").write_text("components: [opencode]")
        (vm_dir / "password").write_text("a" * 32)
        (vm_dir / "certs").mkdir(exist_ok=True)

        rebuild("test-uuid")


class TestVMManagerSync:
    def test_missing_vm_yaml(self) -> None:
        with contextlib.suppress(SystemExit):
            sync("nonexistent-uuid-12345")

    def test_sync_monkeypatched(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr("workspace.cli.vm_manager._podman", _fake_podman_run)
        monkeypatch.setattr("workspace.cli.vm_core._podman", _fake_podman_run)
        vms_dir = _patch_vms_dir(monkeypatch, tmp_path)
        monkeypatch.setattr("workspace.cli.vm_core._VMS_DIR", vms_dir)
        vm_dir = vms_dir / "test-sync"
        vm_dir.mkdir(parents=True, exist_ok=True)
        (vm_dir / "vm.yaml").write_text(
            _yaml.dump({"components": ["opencode"], "sync": [{"dir": str(tmp_path)}]})
        )
        sync("test-sync")


class TestPreCopyFiles:
    def test_empty_files(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        _pre_copy_files(cfg, "test-uuid")


def _fake_subprocess_run(*args, **kwargs):
    class _Result:
        returncode = 0
        stdout = "12345\n"

    return _Result()


def _fake_podman_run(*args, **kwargs):
    class _Result:
        returncode = 0
        stdout = "healthy\n"

    return _Result()


def _patch_vms_dir(monkeypatch, tmp_path: Path) -> MagicMock:
    vms_dir = tmp_path / ".vms"
    vms_dir.mkdir(exist_ok=True)
    monkeypatch.setattr("workspace.cli.vm_core._VMS_DIR", vms_dir)
    monkeypatch.setattr("workspace.cli.vm_manager._VMS_DIR", vms_dir)
    monkeypatch.setattr("workspace.cli.vm_sync._VMS_DIR", vms_dir)
    return vms_dir
