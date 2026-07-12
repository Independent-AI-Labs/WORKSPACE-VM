"""Unit tests for workspace.cli.vpn_core."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workspace.cli import vpn_core


class TestBootName:
    def test_darwin(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.platform, "system", lambda: "Darwin")
        assert vpn_core.boot_name() == ".boot-macos"

    def test_linux(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.platform, "system", lambda: "Linux")
        assert vpn_core.boot_name() == ".boot-linux"


class TestFindWorkspaceRoot:
    def test_finds_root_from_nested_dir(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "workspace").mkdir()
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert vpn_core.find_workspace_root() == tmp_path.resolve()


class TestFindOpenvpnBinary:
    def test_prefers_boot_dir(self, tmp_path: Path) -> None:
        boot = tmp_path / vpn_core.boot_name() / "bin"
        boot.mkdir(parents=True)
        binary = boot / "openvpn"
        binary.write_text("#!/bin/sh\necho openvpn\n")
        binary.chmod(0o755)
        assert vpn_core.find_openvpn_binary(tmp_path) == str(binary.resolve())

    def test_falls_back_to_path(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.shutil, "which", lambda _name: "/usr/bin/openvpn")
        assert vpn_core.find_openvpn_binary(tmp_path) == "/usr/bin/openvpn"

    def test_raises_when_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.shutil, "which", lambda _name: None)
        with pytest.raises(vpn_core._VPNBinaryNotFoundError):
            vpn_core.find_openvpn_binary(tmp_path)


class TestResolveVpnConfig:
    def test_explicit_path(self, tmp_path: Path) -> None:
        cfg = tmp_path / "client.ovpn"
        cfg.write_text("remote vpn.example.com\n")
        resolved = vpn_core.resolve_vpn_config(tmp_path, str(cfg))
        assert resolved == cfg.resolve()

    def test_explicit_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(vpn_core._VPNConfigNotFoundError):
            vpn_core.resolve_vpn_config(tmp_path, str(tmp_path / "missing.ovpn"))

    def test_env_var_path(self, tmp_path: Path, monkeypatch) -> None:
        cfg = tmp_path / "env.ovpn"
        cfg.write_text("remote vpn.example.com\n")
        monkeypatch.setenv(vpn_core.OPENVPN_CONFIG_ENV, str(cfg))
        assert vpn_core.resolve_vpn_config(tmp_path) == cfg.resolve()

    def test_env_var_missing_raises(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv(vpn_core.OPENVPN_CONFIG_ENV, str(tmp_path / "missing.ovpn"))
        with pytest.raises(vpn_core._VPNConfigNotFoundError):
            vpn_core.resolve_vpn_config(tmp_path)

    def test_canonical_default(self, tmp_path: Path) -> None:
        cfg = tmp_path / "workspace/config/vpn/client.ovpn"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("remote vpn.example.com\n")
        resolved = vpn_core.resolve_vpn_config(tmp_path)
        assert resolved == cfg.resolve()

    def test_canonical_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(vpn_core._VPNConfigNotFoundError):
            vpn_core.resolve_vpn_config(tmp_path)


class TestResolveVpnAuth:
    def test_explicit_and_env_and_default(self, tmp_path: Path, monkeypatch) -> None:
        auth = tmp_path / "auth.txt"
        auth.write_text("user\npass\n")
        assert vpn_core.resolve_vpn_auth(tmp_path, str(auth)) == auth.resolve()
        assert vpn_core.resolve_vpn_auth(tmp_path, str(tmp_path / "nope")) is None

        monkeypatch.setenv(vpn_core.OPENVPN_AUTH_ENV, str(auth))
        assert vpn_core.resolve_vpn_auth(tmp_path) == auth.resolve()

        canonical = tmp_path / "workspace/config/vpn/auth.txt"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("user\npass\n")
        monkeypatch.delenv(vpn_core.OPENVPN_AUTH_ENV, raising=False)
        assert vpn_core.resolve_vpn_auth(tmp_path) == canonical.resolve()


class TestValidateOvpn:
    def test_accepts_valid_config(self, tmp_path: Path) -> None:
        path = tmp_path / "client.ovpn"
        path.write_text("remote 10.0.0.1\nproto udp\ndev tun\n")
        assert vpn_core.validate_ovpn(path) is True

    def test_rejects_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "client.ovpn"
        path.write_text("comment only\n")
        assert vpn_core.validate_ovpn(path) is False

    def test_rejects_missing_path(self, tmp_path: Path) -> None:
        assert vpn_core.validate_ovpn(tmp_path / "missing.ovpn") is False


class TestTunnelInterfaceUp:
    def test_darwin_utun(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "darwin")

        def _run(cmd, **kwargs):
            assert cmd == ["ifconfig", "-l"]
            result = MagicMock()
            result.returncode = 0
            result.stdout = "lo0 utun0 en0"
            return result

        monkeypatch.setattr(subprocess, "run", _run)
        assert vpn_core.tunnel_interface_up() is True

    def test_darwin_no_utun(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "darwin")

        def _run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "lo0 en0"
            return result

        monkeypatch.setattr(subprocess, "run", _run)
        assert vpn_core.tunnel_interface_up() is False

    def test_darwin_command_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "darwin")

        def _fail(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(subprocess, "run", _fail)
        assert vpn_core.tunnel_interface_up() is False

    def test_linux_tun0(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "linux")

        def _run(cmd, **kwargs):
            assert cmd == ["ip", "addr", "show", "tun0"]
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr(subprocess, "run", _run)
        assert vpn_core.tunnel_interface_up() is True

    def test_linux_probe_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "linux")

        def _fail(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(subprocess, "run", _fail)
        assert vpn_core.tunnel_interface_up() is False


class TestVpnConnected:
    def test_requires_tunnel_and_workspace_process(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        cfg = tmp_path / "workspace/config/vpn/client.ovpn"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("remote x\n")

        monkeypatch.setattr(vpn_core, "workspace_openvpn_running", lambda _r: True)
        monkeypatch.setattr(vpn_core, "tunnel_interface_up", lambda: True)
        assert vpn_core.vpn_connected(tmp_path) is True

        monkeypatch.setattr(vpn_core, "workspace_openvpn_running", lambda _r: False)
        monkeypatch.setattr(vpn_core, "_recent_log_connected", lambda _lines=20: False)
        monkeypatch.setattr(vpn_core, "tunnel_interface_up", lambda: True)
        assert vpn_core.vpn_connected(tmp_path) is False

    def test_no_tunnel_means_disconnected(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core, "tunnel_interface_up", lambda: False)
        assert vpn_core.vpn_connected(tmp_path) is False

    def test_recent_log_connected(self, tmp_path: Path, monkeypatch) -> None:
        log = tmp_path / "openvpn.log"
        log.write_text("Initialization Sequence Completed\n")
        monkeypatch.setattr(vpn_core, "vpn_log_path", lambda: log)
        monkeypatch.setattr(vpn_core, "tunnel_interface_up", lambda: True)
        monkeypatch.setattr(vpn_core, "workspace_openvpn_running", lambda _r: False)
        assert vpn_core.vpn_connected(tmp_path) is True

    def test_workspace_openvpn_running(self, tmp_path: Path, monkeypatch) -> None:
        cfg = tmp_path / "workspace/config/vpn/client.ovpn"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("remote x\n")
        boot = tmp_path / vpn_core.boot_name() / "bin"
        boot.mkdir(parents=True)
        binary = boot / "openvpn"
        binary.write_text("#!/bin/sh\necho openvpn\n")
        binary.chmod(0o755)

        def _run(cmd, **kwargs):
            if cmd[0] == "pgrep":
                return MagicMock(returncode=0)
            raise AssertionError(cmd)

        monkeypatch.setattr(subprocess, "run", _run)
        assert vpn_core.workspace_openvpn_running(tmp_path) is True


class TestHealthResult:
    def test_connected_payload(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core, "vpn_connected", lambda _r: True)
        result = vpn_core.health_result(tmp_path)
        assert result["status"] == "connected"
        assert result["connected"] is True


class TestVpnLogTail:
    def test_emit_tail_from_log(self, tmp_path: Path, monkeypatch) -> None:
        log_file = tmp_path / ".local" / "state" / "workspace" / "openvpn.log"
        log_file.parent.mkdir(parents=True)
        log_file.write_text("line1\nline2\nline3\n")
        monkeypatch.setattr(vpn_core.sys, "platform", "linux")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        buf = io.StringIO()
        vpn_core.emit_vpn_log_tail(2, buf)
        out = buf.getvalue()
        assert "line2" in out
        assert "line3" in out
        assert "line1" not in out

    def test_darwin_log_path(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "darwin")
        assert str(vpn_core.vpn_log_path()) == "/var/log/workspace/openvpn.log"

    def test_missing_log_message(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core, "vpn_log_path", lambda: tmp_path / "missing.log")
        buf = io.StringIO()
        vpn_core.emit_vpn_log_tail(5, buf)
        assert "not created yet" in buf.getvalue()


class TestOpenvpnCmd:
    def test_builds_argv_with_auth(self, tmp_path: Path) -> None:
        config = tmp_path / "client.ovpn"
        auth = tmp_path / "auth.txt"
        cmd = vpn_core.openvpn_cmd("/bin/openvpn", config, auth)
        assert cmd == [
            "/bin/openvpn",
            "--config",
            str(config),
            "--auth-user-pass",
            str(auth),
        ]
