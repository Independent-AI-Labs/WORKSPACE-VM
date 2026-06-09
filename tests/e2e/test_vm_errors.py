"""E2E tests for VM error handling — no build required."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import vm_cmd

pytestmark = pytest.mark.e2e


class TestVMErrors:
    def test_missing_config_file(self) -> None:
        result = vm_cmd("create", "/nonexistent/path/config.yaml")
        assert result.returncode != 0

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("{[[[ this is not valid yaml")
        result = vm_cmd("create", str(bad))
        assert result.returncode != 0

    def test_missing_components(self, tmp_path: Path) -> None:
        no_comp = tmp_path / "nocomp.yaml"
        no_comp.write_text(yaml.dump({"resources": {"memory": "1g"}}))
        result = vm_cmd("create", str(no_comp))
        assert result.returncode != 0

    def test_proxy_requires_url(self, tmp_path: Path) -> None:
        cfg = tmp_path / "proxy.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "components": ["opencode"],
                    "network": {"mode": "bridge", "policy": "proxy"},
                }
            )
        )
        result = vm_cmd("create", str(cfg))
        assert result.returncode != 0

    def test_openvpn_container_requires_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / "vpn.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "components": ["opencode"],
                    "network": {"mode": "openvpn", "vpn_type": "container"},
                }
            )
        )
        result = vm_cmd("create", str(cfg))
        assert result.returncode != 0

    def test_openvpn_netns_requires_name(self, tmp_path: Path) -> None:
        cfg = tmp_path / "vpnnetns.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "components": ["opencode"],
                    "network": {"mode": "openvpn", "vpn_type": "netns"},
                }
            )
        )
        result = vm_cmd("create", str(cfg))
        assert result.returncode != 0

    def test_ssh_custom_requires_files(self, tmp_path: Path) -> None:
        cfg = tmp_path / "ssh.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "components": ["opencode"],
                    "ssh": {"mode": "custom"},
                }
            )
        )
        result = vm_cmd("create", str(cfg))
        assert result.returncode != 0

    def test_help_exits_zero(self) -> None:
        result = vm_cmd("--help")
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()

    def test_unknown_subcommand(self) -> None:
        result = vm_cmd("nonexistent")
        assert result.returncode != 0
        assert "unknown subcommand" in result.stderr.lower()

    def test_no_args_shows_usage(self) -> None:
        result = vm_cmd()
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
