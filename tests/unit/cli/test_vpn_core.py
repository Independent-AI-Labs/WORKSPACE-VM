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

    def test_canonical_default(self, tmp_path: Path) -> None:
        cfg = tmp_path / "workspace/config/vpn/client.ovpn"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("remote vpn.example.com\n")
        resolved = vpn_core.resolve_vpn_config(tmp_path)
        assert resolved == cfg.resolve()


class TestValidateOvpn:
    def test_accepts_valid_config(self, tmp_path: Path) -> None:
        path = tmp_path / "client.ovpn"
        path.write_text("remote 10.0.0.1\nproto udp\ndev tun\n")
        assert vpn_core.validate_ovpn(path) is True

    def test_rejects_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "client.ovpn"
        path.write_text("comment only\n")
        assert vpn_core.validate_ovpn(path) is False


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

    def test_linux_tun0(self, monkeypatch) -> None:
        monkeypatch.setattr(vpn_core.sys, "platform", "linux")

        def _run(cmd, **kwargs):
            assert cmd == ["ip", "addr", "show", "tun0"]
            result = MagicMock()
            result.returncode = 0
            return result

        monkeypatch.setattr(subprocess, "run", _run)
        assert vpn_core.tunnel_interface_up() is True


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
