"""Unit tests for VM Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from workspace.types.vm import VMConfig

_TEMPLATES_DIR = Path("workspace/scripts/templates")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        lstrip_blocks=True,
        trim_blocks=True,
    )


def _render(template_name: str, context: dict[str, object]) -> str:
    return _env().get_template(template_name).render(context)


class TestDockerfileTemplate:
    def test_renders_minimal_config(self) -> None:
        cfg = VMConfig.model_validate(
            {"components": ["uv", "python", "node", "opencode"]}
        )
        ctx: dict[str, object] = {
            "security": cfg.security,
            "credentials": cfg.credentials,
            "ssh": cfg.ssh,
            "network": cfg.network,
            "traefik_enabled": False,
            "network_enabled": False,
            "openvpn_enabled": False,
            "password": "test-pw",
        }
        result = _render("Dockerfile.vm.j2", ctx)
        assert "FROM ubuntu:22.04" in result
        assert "systemctl enable opencode.service" in result
        assert "traefik.service" not in result
        assert "ami-network.service" not in result

    def test_renders_full_config(self) -> None:
        cfg = VMConfig.model_validate(
            {
                "components": ["uv", "python", "node", "opencode", "traefik"],
                "network": {"mode": "bridge", "policy": "internet"},
                "security": {"cap_add": ["NET_ADMIN"]},
            }
        )
        ctx: dict[str, object] = {
            "security": cfg.security,
            "credentials": cfg.credentials,
            "ssh": cfg.ssh,
            "network": cfg.network,
            "traefik_enabled": True,
            "network_enabled": True,
            "openvpn_enabled": False,
            "password": "test-pw",
            "certs": ".vms/test/certs/",
        }
        result = _render("Dockerfile.vm.j2", ctx)
        assert "systemctl enable opencode.service" in result
        assert "systemctl enable traefik.service" in result
        assert "systemctl enable ami-network.service" in result


class TestOpenCodeService:
    def test_password_embedded(self) -> None:
        ctx: dict[str, object] = {
            "password": "my-secret-password",
            "traefik_enabled": False,
            "network_enabled": False,
        }
        result = _render("systemd-opencode.service.j2", ctx)
        assert "OPENCODE_SERVER_PASSWORD=my-secret-password" in result

    def test_traefik_before_clause(self) -> None:
        ctx: dict[str, object] = {
            "password": "pw",
            "traefik_enabled": True,
            "network_enabled": False,
        }
        result = _render("systemd-opencode.service.j2", ctx)
        assert "Before=traefik.service" in result

    def test_no_traefik_before_when_disabled(self) -> None:
        ctx: dict[str, object] = {
            "password": "pw",
            "traefik_enabled": False,
            "network_enabled": False,
        }
        result = _render("systemd-opencode.service.j2", ctx)
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
        ctx: dict[str, object] = {"policy": "proxy", "proxy_url": "http://proxy:3128"}
        result = _render("systemd-ami-network.service.j2", ctx)
        assert "AMI_PROXY_URL=http://proxy:3128" in result


class TestOpenVPNService:
    def test_basic_render(self) -> None:
        result = _render("systemd-openvpn.service.j2", {})
        assert "openvpn" in result.lower()


class TestTemplateExists:
    def test_all_templates_present(self) -> None:
        expected = [
            "Dockerfile.vm.j2",
            "systemd-opencode.service.j2",
            "systemd-ami-network.service.j2",
            "systemd-traefik.service.j2",
            "systemd-openvpn.service.j2",
            "traefik-static.yml.j2",
            "traefik-dynamic.yml.j2",
        ]
        for name in expected:
            assert (_TEMPLATES_DIR / name).exists(), f"missing template: {name}"
