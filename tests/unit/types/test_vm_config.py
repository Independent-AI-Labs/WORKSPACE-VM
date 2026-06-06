"""Unit tests for VM configuration model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from workspace.types.vm import (
    VMConfig,
    VMCredentialsConfig,
    VMNetworkConfig,
    VMSecurityConfig,
    VMSSHConfig,
)

_DEFAULT_CPUS = 2
_DEFAULT_PIDS_LIMIT = 256
_CUSTOM_CPUS = 4


class TestVMConfig:
    def test_minimal_config(self) -> None:
        cfg = VMConfig.model_validate({"components": ["uv", "python", "opencode"]})
        assert cfg.components == ["uv", "python", "opencode"]
        assert cfg.network.mode == "none"
        assert cfg.security.purge_sudo is True
        assert cfg.credentials.mode == "none"
        assert cfg.ssh.mode == "none"
        assert cfg.web_ui is True

    def test_full_config(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["uv", "python", "node", "opencode", "traefik"],
                "extra_apt": ["htop"],
                "resources": {"memory": "8g", "cpus": 4, "pids_limit": 512},
                "provider": {
                    "name": "llama.cpp",
                    "options": {"base_url": "http://10.0.0.1:8080/v1"},
                },
                "credentials": {"mode": "clone"},
                "ssh": {
                    "mode": "custom",
                    "files": ["~/.ssh/id_ed25519", "~/.gitconfig"],
                },
                "files": [{"src": "workspace/", "dst": "/workspace/"}],
                "sync": [
                    {
                        "dir": "workspace/",
                        "strategy": "merge",
                        "exclude": [".git"],
                    }
                ],
                "mounts": ["/host/data:/container/data:ro"],
                "network": {
                    "mode": "bridge",
                    "network_name": "my-net",
                    "policy": "internet",
                    "whitelist": ["1.2.3.4:443", "5.6.7.8:22"],
                },
                "web_ui": True,
                "env": {"OPENCODE_ENABLE_EXA": "1", "MY_VAR": "val"},
                "security": {
                    "purge_sudo": True,
                    "no_new_privileges": True,
                    "read_only_rootfs": False,
                    "cap_drop": ["ALL"],
                    "cap_add": ["NET_ADMIN"],
                },
            }
        )
        assert cfg.resources.memory == "8g"
        assert cfg.resources.cpus == _CUSTOM_CPUS
        assert cfg.provider is not None
        assert cfg.provider.name == "llama.cpp"
        assert cfg.credentials.mode == "clone"
        assert cfg.ssh.mode == "custom"
        assert cfg.ssh.files == ["~/.ssh/id_ed25519", "~/.gitconfig"]
        assert len(cfg.files) == 1
        assert cfg.files[0].src == "workspace/"
        assert cfg.files[0].dst == "/workspace/"
        assert len(cfg.sync) == 1
        assert cfg.sync[0].strategy == "merge"
        assert cfg.network.mode == "bridge"
        assert cfg.network.policy == "internet"
        assert cfg.network.whitelist == ["1.2.3.4:443", "5.6.7.8:22"]
        assert cfg.security.read_only_rootfs is False
        assert cfg.security.cap_add == ["NET_ADMIN"]

    def test_defaults(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        assert cfg.resources.memory == "4g"
        assert cfg.resources.cpus == _DEFAULT_CPUS
        assert cfg.resources.pids_limit == _DEFAULT_PIDS_LIMIT
        assert cfg.network.mode == "none"
        assert cfg.network.policy == "unrestricted"
        assert cfg.web_ui is True
        assert cfg.security.purge_sudo is True
        assert cfg.security.no_new_privileges is True
        assert cfg.security.read_only_rootfs is True
        assert cfg.security.cap_drop == ["ALL"]
        assert cfg.security.cap_add == []
        assert cfg.credentials.mode == "none"
        assert cfg.ssh.mode == "none"
        assert cfg.ssh.files == []

    def test_missing_components(self) -> None:
        with pytest.raises(ValidationError):
            VMConfig.model_validate({})

    def test_empty_components(self) -> None:
        cfg = VMConfig.model_validate({"components": []})
        assert cfg.components == []


class TestVMCredentialsConfig:
    def test_default_mode(self) -> None:
        cfg = VMCredentialsConfig()
        assert cfg.mode == "none"

    def test_invalid_mode(self) -> None:
        with pytest.raises(ValidationError):
            VMCredentialsConfig.model_validate({"mode": "invalid"})


class TestVMSSHConfig:
    def test_default(self) -> None:
        cfg = VMSSHConfig()
        assert cfg.mode == "none"
        assert cfg.files == []

    def test_custom_without_files_fails(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            VMSSHConfig(mode="custom")
        assert exc_info.value.errors()[0]["type"] == "value_error"

    def test_custom_with_files(self) -> None:
        cfg = VMSSHConfig(mode="custom", files=["~/.ssh/id_ed25519"])
        assert cfg.mode == "custom"
        assert cfg.files == ["~/.ssh/id_ed25519"]


class TestVMNetworkConfig:
    def test_default_mode(self) -> None:
        cfg = VMNetworkConfig()
        assert cfg.mode == "none"

    def test_proxy_policy_without_url_fails(self) -> None:
        with pytest.raises(ValidationError):
            VMNetworkConfig(mode="bridge", policy="proxy")

    def test_proxy_policy_with_url(self) -> None:
        cfg = VMNetworkConfig(
            mode="bridge",
            policy="proxy",
            proxy_url="http://proxy:3128",
        )
        assert cfg.proxy_url == "http://proxy:3128"

    def test_openvpn_container_without_config_fails(self) -> None:
        with pytest.raises(ValidationError):
            VMNetworkConfig(mode="openvpn", vpn_type="container")

    def test_openvpn_netns_without_name_fails(self) -> None:
        with pytest.raises(ValidationError):
            VMNetworkConfig(mode="openvpn", vpn_type="netns")

    _vpn_test_config = "/tmp/vpn/client.ovpn"

    def test_openvpn_container_with_config(self) -> None:
        cfg = VMNetworkConfig(
            mode="openvpn",
            vpn_type="container",
            vpn_config=self._vpn_test_config,
        )
        assert cfg.vpn_config == self._vpn_test_config


class TestVMSecurityConfig:
    def test_defaults(self) -> None:
        cfg = VMSecurityConfig()
        assert cfg.purge_sudo is True
        assert cfg.no_new_privileges is True
        assert cfg.read_only_rootfs is True
        assert cfg.cap_drop == ["ALL"]
        assert cfg.cap_add == []

    def test_permissive_config(self) -> None:
        cfg = VMSecurityConfig(
            purge_sudo=False,
            no_new_privileges=False,
            read_only_rootfs=False,
            cap_drop=[],
            cap_add=["ALL"],
        )
        assert cfg.purge_sudo is False
        assert cfg.cap_add == ["ALL"]
