"""Additional guest configuration tests for mounts, files, and credentials."""

from __future__ import annotations

from pathlib import Path

import pytest

from workspace.cli.hypervisor import qemu_guest_config as gc
from workspace.types.vm import VMConfig


def _config(**overrides: object) -> VMConfig:
    data: dict[str, object] = {
        "components": ["uv"],
        "web_ui": False,
        "isolation": {"backend": "qemu", "qemu": {"provision": "none"}},
    }
    data.update(overrides)
    return VMConfig.model_validate(data)


def _vm_dir(tmp_path: Path) -> Path:
    vm_dir = tmp_path / "vm"
    vm_dir.mkdir(exist_ok=True)
    (vm_dir / "ssh_port").write_text("55100")
    (vm_dir / "qemu_ssh_ed25519").write_text("key")
    return vm_dir


def test_apply_guest_config_reads_ssh_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    gc.apply_guest_config(_config(), _vm_dir(tmp_path))
    assert any("DefaultTasksMax" in script for script in scripts)


def test_apply_env_rejects_invalid_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="invalid environment key"):
        gc._apply_env(55100, tmp_path / "key", {"BAD KEY": "value"})


def test_apply_files_missing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    cfg = _config(files=[{"src": str(tmp_path / "absent"), "dst": "notes.txt"}])
    with pytest.raises(FileNotFoundError, match="file source not found"):
        gc._apply_files(55100, tmp_path / "key", cfg)


def test_apply_files_copies_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    calls: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    monkeypatch.setattr(gc, "_rsync", lambda _p, _k, src, dst: calls.append(str(dst)))
    cfg = _config(files=[{"src": str(source), "dst": "notes.txt"}])
    gc._apply_files(55100, tmp_path / "key", cfg)
    assert calls == ["/opt/workspace/notes.txt"]


def test_apply_ssh_inherit_copies_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    (home / ".ssh" / "id_ed25519").write_text("key")
    monkeypatch.setenv("HOME", str(home))
    copies: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    monkeypatch.setattr(gc, "_copy_file", lambda _p, _k, src, dst: copies.append(dst))
    gc._apply_ssh(55100, tmp_path / "key", _config(ssh={"mode": "inherit"}))
    assert copies == [".ssh/id_ed25519"]


def test_apply_ssh_custom_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    cfg = _config(ssh={"mode": "custom", "files": [str(tmp_path / "absent")]})
    with pytest.raises(FileNotFoundError, match="SSH file not found"):
        gc._apply_ssh(55100, tmp_path / "key", cfg)


def test_apply_provider_writes_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    cfg = _config(provider={"name": "local", "options": {"baseURL": "http://x"}})
    gc._apply_provider(55100, tmp_path / "key", cfg)
    assert "base64 -d" in scripts[0]
    assert "local" not in scripts[0]


def test_apply_credentials_clone_missing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    with pytest.raises(FileNotFoundError, match="credentials source not found"):
        gc._apply_credentials(
            55100, tmp_path / "key", _config(credentials={"mode": "clone"})
        )


def test_apply_credentials_clone_rsyncs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    source = home / ".config" / "opencode"
    source.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    calls: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda *_a, **_k: None)
    monkeypatch.setattr(gc, "_rsync", lambda _p, _k, _src, dst: calls.append(dst))
    gc._apply_credentials(
        55100, tmp_path / "key", _config(credentials={"mode": "clone"})
    )
    assert calls == ["~/.config/opencode/"]


def test_proxy_host_rejects_empty_url() -> None:
    with pytest.raises(ValueError, match="invalid proxy URL"):
        gc._proxy_host("http://")


def test_apply_openvpn_copies_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "client.ovpn"
    config.write_text("client")
    auth = tmp_path / "auth.txt"
    auth.write_text("user")
    scripts: list[str] = []
    copies: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    monkeypatch.setattr(gc, "_copy_file", lambda _p, _k, src, dst: copies.append(dst))
    monkeypatch.setattr(gc, "find_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(gc, "resolve_vpn_config", lambda *_a: config)
    monkeypatch.setattr(gc, "resolve_vpn_auth", lambda *_a: auth)
    cfg = _config(
        network={
            "mode": "openvpn",
            "vpn_type": "container",
            "vpn_config": "client.ovpn",
            "vpn_auth": "auth.txt",
        }
    )
    gc._apply_openvpn(55100, tmp_path / "key", cfg, tmp_path)
    assert copies == [
        "/tmp/workspace-openvpn-client.ovpn",
        "/tmp/workspace-openvpn-auth.txt",
    ]
    assert "--auth-user-pass" in scripts[0]


def test_apply_host_shares_mounts_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    gc.apply_host_shares(_vm_dir(tmp_path), with_ci=True)
    assert "workspace-ci" in scripts[0]
    assert "/mnt/workspace-ro" in scripts[0]


def test_apply_mounts_reads_port_and_skips_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    monkeypatch.setattr(gc, "_ssh", lambda _p, _k, script: scripts.append(script))
    gc.apply_mounts(_config(), _vm_dir(tmp_path))
    assert scripts == []
    mount = tmp_path / "share"
    mount.mkdir()
    gc.apply_mounts(_config(mounts=[str(mount)]), _vm_dir(tmp_path))
    assert "hostshare0" in scripts[0]
