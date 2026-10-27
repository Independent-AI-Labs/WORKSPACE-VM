from __future__ import annotations

from pathlib import Path

import pytest

from workspace.cli.hypervisor import qemu_guest_config as gc
from workspace.types.vm import VMConfig


def _config(tmp_path: Path, **overrides: object) -> VMConfig:
    data = {
        "components": ["uv"],
        "web_ui": False,
        "mounts": [str(tmp_path)],
        "env": {"TOKEN": "value"},
        "isolation": {
            "backend": "qemu",
            "qemu": {"guest_arch": "aarch64", "provision": "none"},
        },
    }
    data.update(overrides)
    return VMConfig.model_validate(data)


def test_apply_configures_mounts_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    key = tmp_path / "qemu_ssh_ed25519"
    key.write_text("key")

    gc.apply_guest_config(_config(tmp_path), tmp_path, ssh_port=55222)

    joined = "\n".join(scripts)
    assert "hostshare0" in joined
    assert str(tmp_path) in joined
    assert "TOKEN=value" in joined


def test_destination_rejects_traversal() -> None:
    with pytest.raises(ValueError, match="invalid guest destination"):
        gc._destination("../escape")


def test_credentials_api_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    cfg = _config(tmp_path, credentials={"mode": "api"})
    with pytest.raises(ValueError, match=r"credentials\.mode api"):
        gc.apply_guest_config(cfg, tmp_path, ssh_port=55222)


def test_web_ui_writes_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    (tmp_path / "password").write_text("secret\n")
    cfg = _config(tmp_path, web_ui=True)
    gc.apply_guest_config(cfg, tmp_path, ssh_port=55222)
    assert "opencode.service" in "\n".join(scripts)
    assert "OPENCODE_SERVER_PASSWORD=secret" in "\n".join(scripts)


def test_openvpn_writes_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    monkeypatch.setattr(gc, "_copy_file", lambda *_a, **_k: None)
    monkeypatch.setattr(gc, "find_workspace_root", lambda: tmp_path)
    vpn = tmp_path / "client.ovpn"
    vpn.write_text("client\n")
    monkeypatch.setattr(gc, "resolve_vpn_config", lambda *_a: vpn)
    monkeypatch.setattr(gc, "resolve_vpn_auth", lambda *_a: None)
    cfg = _config(
        tmp_path,
        network={
            "mode": "openvpn",
            "vpn_type": "container",
            "vpn_config": "client.ovpn",
        },
    )
    gc.apply_guest_config(cfg, tmp_path, ssh_port=55222)
    assert "openvpn.service" in "\n".join(scripts)


def test_bridge_internet_policy_writes_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    cfg = _config(
        tmp_path,
        network={"mode": "bridge", "policy": "internet", "network_name": "br0"},
    )
    gc.apply_guest_config(cfg, tmp_path, ssh_port=55222)
    joined = "\n".join(scripts)
    assert "vm-network-policy" in joined
    assert "10.0.0.0/8" in joined


def test_bridge_proxy_policy_sets_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    cfg = _config(
        tmp_path,
        network={
            "mode": "bridge",
            "policy": "proxy",
            "network_name": "br0",
            "proxy_url": "http://proxy.local:3128",
        },
    )
    gc.apply_guest_config(cfg, tmp_path, ssh_port=55222)
    joined = "\n".join(scripts)
    assert "HTTP_PROXY=http://proxy.local:3128" in joined
    assert "getent ahostsv4 proxy.local" in joined
