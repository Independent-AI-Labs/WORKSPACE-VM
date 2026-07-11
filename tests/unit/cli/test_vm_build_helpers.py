"""Unit tests for vm_build and vm_core helpers added for macOS support."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workspace.cli.vm_build import (
    _build_context,
    _derive_network_flags,
    _generate_companion_files,
    _prepare_build_ssh_key,
    _render_and_build,
)
from workspace.cli.vm_core import (
    _config_sha256,
    _ensure_podman_machine,
    _podman,
    _PodmanMachineError,
    _remove_hosts_entry,
)
from workspace.types.vm import (
    VM_CONTAINER_HOME,
    VM_CONTAINER_USER,
    VM_INSTALL_ROOT,
    VMConfig,
)

_SHA256_HEX_LEN = 16


class TestPrepareBuildSshKey:
    def test_creates_empty_key_when_no_host_key(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        vm_dir = tmp_path / ".vms" / "uuid"
        vm_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "empty-home")
        (tmp_path / "empty-home").mkdir()

        rel = _prepare_build_ssh_key(vm_dir)

        assert (vm_dir / "temp_ssh_key").exists()
        assert rel.endswith(".vms/uuid/temp_ssh_key")

    def test_copies_host_key_when_present(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        home = tmp_path / "home"
        ssh_dir = home / ".ssh"
        ssh_dir.mkdir(parents=True)
        src = ssh_dir / "id_rsa"
        src.write_text("fake-key")
        monkeypatch.setattr(Path, "home", lambda: home)

        vm_dir = tmp_path / ".vms" / "uuid"
        vm_dir.mkdir(parents=True)
        rel = _prepare_build_ssh_key(vm_dir)

        dest = vm_dir / "temp_ssh_key"
        assert dest.read_text() == "fake-key"
        assert oct(dest.stat().st_mode & 0o777) == oct(0o600)
        assert rel.endswith("temp_ssh_key")


class TestBuildContext:
    def test_includes_workspace_constants(self, tmp_path: Path) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode", "traefik"],
                "network": {
                    "mode": "bridge",
                    "policy": "proxy",
                    "proxy_url": "http://proxy:3128",
                },
            }
        )
        vm_dir = tmp_path / "vm"
        vm_dir.mkdir()
        ctx = _build_context(cfg, "pw", vm_dir, tmp_path / "defaults.yaml", "key/path")

        assert ctx["container_user"] == VM_CONTAINER_USER
        assert ctx["container_home"] == VM_CONTAINER_HOME
        assert ctx["container_install_root"] == VM_INSTALL_ROOT
        assert ctx["traefik_enabled"] is True
        assert ctx["network_enabled"] is True
        assert ctx["policy"] == "proxy"


class TestGenerateCompanionFiles:
    def test_writes_openvpn_service(self, tmp_path: Path) -> None:
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
        vm_dir = tmp_path / "vm"
        vm_dir.mkdir()
        ctx = _build_context(cfg, "pw", vm_dir, tmp_path / "defaults.yaml", "key/path")

        _generate_companion_files(vm_dir, cfg, ctx)

        assert (vm_dir / "vm-openvpn.service").exists()

    def test_writes_traefik_and_network_services(self, tmp_path: Path) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode", "traefik"],
                "network": {"mode": "bridge", "policy": "internet"},
            }
        )
        vm_dir = tmp_path / "vm"
        vm_dir.mkdir()
        ctx = _build_context(cfg, "pw", vm_dir, tmp_path / "defaults.yaml", "key/path")

        _generate_companion_files(vm_dir, cfg, ctx)

        assert (vm_dir / "vm-opencode.json").exists()
        assert (vm_dir / "vm-traefik.service").exists()
        assert (vm_dir / "vm-workspace-network.service").exists()


class TestRenderAndBuild:
    def test_cleans_up_ssh_key_after_build(self, tmp_path: Path, monkeypatch) -> None:
        vm_dir = tmp_path / "vm"
        vm_dir.mkdir()
        ssh_key = vm_dir / "temp_ssh_key"
        ssh_key.write_text("key")
        calls: list[tuple[str, ...]] = []

        def _fake_podman(*args: str) -> MagicMock:
            calls.append(args)
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr("workspace.cli.vm_build._podman", _fake_podman)
        monkeypatch.setattr("workspace.cli.vm_build._get_uid", lambda: "1000")

        cfg = VMConfig.model_validate({"components": ["opencode"]})
        ctx = _build_context(cfg, "pw", vm_dir, tmp_path / "defaults.yaml", "key/path")
        _render_and_build("uuid", "pw", vm_dir, ctx)

        assert not ssh_key.exists()
        assert calls
        build_args = calls[0]
        if sys.platform == "darwin":
            assert "--ssh" not in build_args
        else:
            assert "--ssh" in build_args
        assert "workspace-vm:uuid" in build_args


class TestDeriveNetworkFlagsOpenvpnContainer:
    def test_openvpn_container_uses_bridge_network(self) -> None:
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
        flags = _derive_network_flags(cfg)
        assert "workspace-vm-net" in flags
        assert "--device" in flags
        assert "/dev/net/tun" in flags


class TestConfigSha256String:
    def test_hashes_raw_string(self) -> None:
        digest = _config_sha256('{"components":["opencode"]}')
        assert len(digest) == _SHA256_HEX_LEN
        assert digest == _config_sha256('{"components":["opencode"]}')


class TestRemoveHostsEntry:
    def test_removes_matching_line(self, tmp_path: Path, monkeypatch) -> None:
        hosts = tmp_path / "hosts"
        hosts.write_text("127.0.0.1 localhost\n10.0.0.1 myuuid.vm.local\n")
        real_path = Path

        def patched_path(arg: str | None = None) -> Path:
            if arg == "/etc/hosts":
                return real_path(hosts)
            if arg is None:
                return real_path()
            return real_path(arg)

        monkeypatch.setattr("workspace.cli.vm_core.Path", patched_path)
        _remove_hosts_entry("myuuid")
        content = hosts.read_text()
        assert "myuuid.vm.local" not in content
        assert "localhost" in content


class TestPodmanErrorOutput:
    def test_writes_stderr_on_failure(self, monkeypatch, capsys) -> None:
        def _fail(*args, **kwargs):
            exc = subprocess.CalledProcessError(1, args[0])
            exc.stderr = "podman failed\n"
            exc.stdout = ""
            raise exc

        monkeypatch.setattr(subprocess, "run", _fail)
        with pytest.raises(subprocess.CalledProcessError):
            _podman("version")
        assert "podman failed" in capsys.readouterr().err


class TestEnsurePodmanMachine:
    def test_noop_on_linux(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        _ensure_podman_machine()

    def test_raises_when_machine_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")

        def _fail(*args, **kwargs):
            raise subprocess.CalledProcessError(1, args[0])

        monkeypatch.setattr(subprocess, "run", _fail)
        with pytest.raises(_PodmanMachineError, match="not configured"):
            _ensure_podman_machine()

    def test_raises_when_machine_not_running(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")

        def _run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "--format" in cmd:
                result.stdout = "stopped\n"
            else:
                result.stdout = ""
            return result

        monkeypatch.setattr(subprocess, "run", _run)
        with pytest.raises(_PodmanMachineError, match="not running"):
            _ensure_podman_machine()
