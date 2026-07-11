"""Unit tests for VM Jinja2 templates."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from workspace.types.vm import (
    VM_CONTAINER_HOME,
    VM_CONTAINER_USER,
    VM_INSTALL_ROOT,
    VMConfig,
    VMCredentialsConfig,
    VMNetworkConfig,
    VMSecurityConfig,
    VMSSHConfig,
)

VmTemplateValue = (
    str
    | bool
    | VMConfig
    | VMSecurityConfig
    | VMCredentialsConfig
    | VMSSHConfig
    | VMNetworkConfig
)

_TEMPLATES_DIR = Path("workspace/scripts/templates")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        lstrip_blocks=True,
        trim_blocks=True,
    )


def _base_ctx(cfg: VMConfig, **extra: VmTemplateValue) -> Mapping[str, VmTemplateValue]:
    ctx: dict[str, VmTemplateValue] = {
        "security": cfg.security,
        "credentials": cfg.credentials,
        "ssh": cfg.ssh,
        "network": cfg.network,
        "traefik_enabled": False,
        "network_enabled": False,
        "openvpn_enabled": False,
        "password": "test-pw",
        "container_user": VM_CONTAINER_USER,
        "container_home": VM_CONTAINER_HOME,
        "container_install_root": VM_INSTALL_ROOT,
        "policy": cfg.network.policy,
        "proxy_url": cfg.network.proxy_url,
        "vm_temp_ssh_key_relpath": ".vms/test-uuid/temp_ssh_key",
        "vm_install_defaults": ".vms/test-uuid/vm-install-defaults.yaml",
        "vm_opencode_json": ".vms/test-uuid/vm-opencode.json",
        "vm_opencode_service": ".vms/test-uuid/vm-opencode.service",
        "vm_traefik_service": ".vms/test-uuid/vm-traefik.service",
        "vm_traefik_static": ".vms/test-uuid/vm-traefik-static.yml",
        "vm_traefik_dynamic": ".vms/test-uuid/vm-traefik-dynamic.yml",
        "vm_workspace_network_service": ".vms/test-uuid/vm-workspace-network.service",
        "vm_openvpn_service": ".vms/test-uuid/vm-openvpn.service",
    }
    ctx.update(extra)
    return ctx


def _render(template_name: str, context: Mapping[str, VmTemplateValue]) -> str:
    return _env().get_template(template_name).render(context)


class TestDockerfileTemplate:
    def test_renders_minimal_config(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["uv", "python", "node", "opencode"]}
        )
        result = _render("Dockerfile.vm.j2", _base_ctx(cfg))
        assert "FROM ubuntu:22.04" in result
        assert "systemctl enable opencode.service" in result
        assert "traefik.service" not in result
        assert "workspace-network.service" not in result
        assert "curl -skf https://localhost:443/" in result
        assert 'ENTRYPOINT ["/lib/systemd/systemd"]' in result

    def test_renders_full_config(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["uv", "python", "node", "opencode", "traefik"],
                "network": {"mode": "bridge", "policy": "internet"},
                "security": {"cap_add": ["NET_ADMIN"]},
            }
        )
        result = _render(
            "Dockerfile.vm.j2",
            _base_ctx(
                cfg,
                traefik_enabled=True,
                network_enabled=True,
                certs=".vms/test/certs/",
            ),
        )
        assert "systemctl enable opencode.service" in result
        assert "systemctl enable traefik.service" in result
        assert "systemctl enable workspace-network.service" in result


class TestOpenCodeService:
    def test_password_embedded(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        result = _render("systemd-opencode.service.j2", _base_ctx(cfg))
        assert "OPENCODE_SERVER_PASSWORD=test-pw" in result

    def test_traefik_before_clause(self) -> None:
        result = _render(
            "systemd-opencode.service.j2",
            _base_ctx(
                VMConfig.model_validate({"components": ["opencode"]}),
                traefik_enabled=True,
            ),
        )
        assert "Before=traefik.service" in result

    def test_no_traefik_before_when_disabled(self) -> None:
        cfg = VMConfig.model_validate({"components": ["opencode"]})
        result = _render("systemd-opencode.service.j2", _base_ctx(cfg))
        assert "Before=traefik.service" not in result


class TestTraefikConfigs:
    def test_static_config_minimal(self) -> None:
        result = _render("traefik-static.yml.j2", {})
        parsed = yaml.safe_load(result)
        assert parsed["entryPoints"]["websecure"]["address"] == ":443"

    def test_dynamic_config_minimal(self) -> None:
        result = _render("traefik-dynamic.yml.j2", {})
        parsed = yaml.safe_load(result)
        servers = parsed["http"]["services"]["opencode"]["loadBalancer"]["servers"]
        assert servers[0]["url"] == "http://127.0.0.1:4096"


class TestNetworkService:
    def test_proxy_policy(self) -> None:
        ctx: dict[str, str] = {"policy": "proxy", "proxy_url": "http://proxy:3128"}
        result = _render("systemd-workspace-network.service.j2", ctx)
        assert "WORKSPACE_PROXY_URL=http://proxy:3128" in result


class TestOpenVPNService:
    def test_basic_render(self) -> None:
        result = _render("systemd-openvpn.service.j2", {})
        assert "openvpn" in result.lower()


class TestTemplateExists:
    def test_all_templates_present(self) -> None:
        expected = [
            "Dockerfile.vm.j2",
            "systemd-opencode.service.j2",
            "systemd-workspace-network.service.j2",
            "systemd-traefik.service.j2",
            "systemd-openvpn.service.j2",
            "traefik-static.yml.j2",
            "traefik-dynamic.yml.j2",
        ]
        for name in expected:
            assert (_TEMPLATES_DIR / name).exists(), f"missing template: {name}"
