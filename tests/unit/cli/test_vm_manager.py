"""Unit tests for vm_manager helper functions (no podman required)."""

from __future__ import annotations

import subprocess

from workspace.cli.vm_manager import (
    _config_sha256,
    _derive_cap_flags,
    _derive_network_flags,
    _generate_password,
    _get_uid,
    _podman,
    _render_template,
)
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
        assert "ami-vm-net" in flags

    def test_host_mode(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["opencode"], "network": {"mode": "host"}}
        )
        flags = _derive_network_flags(cfg)
        assert flags == ["--network", "host"]

    def test_openvpn_netns(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["opencode"],
                "network": {
                    "mode": "openvpn",
                    "vpn_type": "netns",
                    "vpn_netns": "myvpn",
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
    def test_podman_wrapper(self) -> None:
        result = _podman("version")
        assert result.returncode == 0
        assert "Version:" in result.stdout


class TestGetUid:
    def test_returns_digit_string(self) -> None:
        uid = _get_uid()
        assert uid.isdigit()
        assert len(uid) > 0
