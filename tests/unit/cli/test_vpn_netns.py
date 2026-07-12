"""Unit tests for workspace.cli.vpn_netns."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from workspace.cli import vpn_core
from workspace.cli.vpn_netns import _VPNNetnsSetupError, ensure_vpn_netns
from workspace.types.vm import VMConfig, VMNetworkConfig


class TestEnsureVpnNetns:
    def test_invokes_setup_script(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "platform", "linux")
        (tmp_path / "workspace/scripts/bin").mkdir(parents=True)
        script = tmp_path / "workspace/scripts/bin/setup_vpn_netns.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(0o755)

        cfg_path = tmp_path / "client.ovpn"
        cfg_path.write_text("remote vpn.example.com\nproto udp\ndev tun\n")
        boot = tmp_path / vpn_core.boot_name() / "bin"
        boot.mkdir(parents=True)
        binary = boot / "openvpn"
        binary.write_text("#!/bin/sh\necho openvpn\n")
        binary.chmod(0o755)

        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {
                    "mode": "openvpn",
                    "vpn_type": "netns",
                    "vpn_netns": "workspace-vpn",
                    "vpn_config": str(cfg_path),
                },
            }
        )

        calls: list[list[str]] = []

        def _run(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", _run)
        ensure_vpn_netns(cfg, tmp_path)
        assert calls
        assert calls[0][0] == "bash"
        assert "--netns" in calls[0]
        assert "workspace-vpn" in calls[0]

    def test_wraps_subprocess_failure(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "platform", "linux")
        (tmp_path / "workspace/scripts/bin").mkdir(parents=True)
        script = tmp_path / "workspace/scripts/bin/setup_vpn_netns.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(0o755)

        cfg_path = tmp_path / "client.ovpn"
        cfg_path.write_text("remote vpn.example.com\nproto udp\ndev tun\n")
        boot = tmp_path / vpn_core.boot_name() / "bin"
        boot.mkdir(parents=True)
        binary = boot / "openvpn"
        binary.write_text("#!/bin/sh\necho openvpn\n")
        binary.chmod(0o755)

        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {
                    "mode": "openvpn",
                    "vpn_type": "netns",
                    "vpn_netns": "workspace-vpn",
                    "vpn_config": str(cfg_path),
                },
            }
        )

        def _fail(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(subprocess, "run", _fail)
        with pytest.raises(_VPNNetnsSetupError, match="sudo"):
            ensure_vpn_netns(cfg, tmp_path)

    def test_noop_on_darwin(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        cfg = VMConfig.model_construct(
            components=["opencode"],
            network=VMNetworkConfig.model_construct(
                mode="openvpn",
                vpn_type="netns",
                vpn_netns="workspace-vpn",
                vpn_config="/tmp/client.ovpn",
            ),
        )
        ensure_vpn_netns(cfg, Path("/tmp"))


class TestDarwinNetnsSchema:
    def test_rejects_netns_on_darwin(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        with pytest.raises(ValidationError):
            VMConfig.model_validate(
                {
                    "components": ["opencode"],
                    "network": {
                        "mode": "openvpn",
                        "vpn_type": "netns",
                        "vpn_netns": "workspace-vpn",
                        "vpn_config": "/tmp/client.ovpn",
                    },
                }
            )
