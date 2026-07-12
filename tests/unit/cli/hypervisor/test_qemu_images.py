"""Unit tests for qemu_images."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from workspace.cli.hypervisor import qemu_images as qi
from workspace.cli.vpn_core import find_workspace_root
from workspace.types.vm import VMConfig

_HAS_ISO_TOOL = (
    shutil.which("genisoimage") is not None or shutil.which("mkisofs") is not None
)
_skip_no_iso_tool = pytest.mark.skipif(
    not _HAS_ISO_TOOL,
    reason="genisoimage/mkisofs not installed; run: sudo make install-qemu",
)

_TEST_SHA = "ab" * 32
_REQUESTED_PORT = 55222
_MIN_EPHEMERAL_PORT = 1024
_MAX_EPHEMERAL_PORT = 65535


def test_image_key() -> None:
    assert qi._image_key("aarch64") == "ubuntu_2404_arm64"
    assert qi._image_key("x86_64") == "ubuntu_2404_x86_64"


def test_allocate_ssh_port_requested() -> None:
    assert qi.allocate_ssh_port(_REQUESTED_PORT) == _REQUESTED_PORT


def test_allocate_ssh_port_ephemeral() -> None:
    port = qi.allocate_ssh_port(0)
    assert _MIN_EPHEMERAL_PORT <= port <= _MAX_EPHEMERAL_PORT


def test_verify_sha256_match(tmp_path: Path) -> None:
    payload = b"cloud-image"
    path = tmp_path / "img.raw"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    qi._verify_sha256(path, digest)


def test_verify_sha256_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "img.raw"
    path.write_bytes(b"bad")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        qi._verify_sha256(path, _TEST_SHA)


def test_ensure_base_image_missing_pin_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "_base"
    base.mkdir()
    monkeypatch.setattr(qi, "_VMS_BASE", base)

    def _empty_pins() -> qi.QemuPinsManifest:
        return qi.QemuPinsManifest()

    monkeypatch.setattr(qi, "_load_pins", _empty_pins)
    with pytest.raises(FileNotFoundError, match="no image pin"):
        qi.ensure_base_image("missing.qcow2", "aarch64")


def test_ensure_base_image_cache_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "_base"
    base.mkdir()
    cached = base / "workspace-vm-base-ubuntu-24.04-aarch64.qcow2"
    cached.write_bytes(b"qcow2")
    monkeypatch.setattr(qi, "_VMS_BASE", base)
    result = qi.ensure_base_image(cached.name, "aarch64")
    assert result == cached


def test_prepare_vm_storage_writes_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vm_dir = tmp_path / "vm"
    vm_dir.mkdir()
    cfg = VMConfig.model_validate(
        {
            "components": ["uv"],
            "isolation": {
                "backend": "qemu",
                "qemu": {
                    "guest_arch": "aarch64",
                    "image": "workspace-vm-base-ubuntu-24.04-aarch64.qcow2",
                    "ssh_host_port": 55001,
                    "provision": "none",
                },
            },
        }
    )
    monkeypatch.setattr(
        qi, "ensure_base_image", lambda *_a, **_k: tmp_path / "base.qcow2"
    )
    monkeypatch.setattr(qi, "create_overlay", lambda *_a, **_k: None)
    monkeypatch.setattr(qi, "generate_ssh_keypair", lambda _d: (vm_dir / "key", "pub"))
    monkeypatch.setattr(qi, "write_cloud_init", lambda *_a, **_k: None)

    port = qi.prepare_vm_storage(cfg, vm_dir)
    assert port == "55001"
    assert (vm_dir / "ssh_port").read_text() == "55001"


def test_load_pins_missing_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(qi, "find_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(qi, "_PINS_PATH", Path("res/qemu-pins.yaml"))
    assert qi._load_pins().images == {}


def test_ensure_base_image_downloads_and_converts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "_base"
    base.mkdir()
    monkeypatch.setattr(qi, "_VMS_BASE", base)
    monkeypatch.setattr(
        qi,
        "_load_pins",
        lambda: qi.QemuPinsManifest.model_validate(
            {
                "images": {
                    "ubuntu_2404_arm64": {
                        "url": "https://example.com/img",
                        "sha256": "",
                    }
                }
            }
        ),
    )
    raw = base / ".download-ubuntu_2404_arm64.img"
    dest = base / "workspace-vm-base-ubuntu-24.04-aarch64.qcow2"

    def _fake_download(url: str, path: Path) -> None:
        path.write_bytes(b"raw")

    monkeypatch.setattr(qi, "_download_file", _fake_download)
    monkeypatch.setattr(qi, "_resolve_qemu_img", lambda: Path("/opt/qemu-img"))
    monkeypatch.setattr(
        qi.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess("qemu-img", 0, "", ""),
    )
    result = qi.ensure_base_image(dest.name, "aarch64")
    assert result == dest
    assert not raw.exists()


def test_create_overlay_invokes_qemu_img(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "base.qcow2"
    base.write_bytes(b"base")
    overlay = tmp_path / "overlay.qcow2"
    calls: list[list[str]] = []

    def _fake_run(
        cmd: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(qi, "_resolve_qemu_img", lambda: Path("/opt/qemu-img"))
    monkeypatch.setattr(qi.subprocess, "run", _fake_run)
    qi.create_overlay(base, overlay, disk_gb=20)
    assert calls[0][1] == "create"
    assert calls[1][1] == "resize"


@_skip_no_iso_tool
def test_write_cloud_init_mount_workspace(tmp_path: Path) -> None:
    vm_dir = tmp_path / "vm"
    qi.write_cloud_init(vm_dir, "ssh-rsa AAA", mount_workspace=True)
    user_data = (vm_dir / "cloud-init" / "user-data").read_text()
    assert user_data.startswith("#cloud-config\n")
    config = yaml.safe_load(user_data.removeprefix("#cloud-config\n"))
    assert any("9p" in cmd for cmd in config["runcmd"])
    assert "rsync" in config["packages"]
    assert (vm_dir / "cloud-init" / "seed.img").is_file()


@_skip_no_iso_tool
def test_write_cloud_init_no_mount(tmp_path: Path) -> None:
    vm_dir = tmp_path / "vm"
    qi.write_cloud_init(vm_dir, "ssh-rsa AAA", mount_workspace=False)
    user_data = (vm_dir / "cloud-init" / "user-data").read_text()
    assert "rsync" not in user_data


def test_generate_ssh_keypair_reuses_existing(tmp_path: Path) -> None:
    key = tmp_path / "qemu_ssh_ed25519"
    key.write_text("private")
    (tmp_path / "qemu_ssh_ed25519.pub").write_text("ssh-ed25519 AAA")
    path, pub = qi.generate_ssh_keypair(tmp_path)
    assert path == key
    assert pub == "ssh-ed25519 AAA"


def test_qemu_pins_no_pending_sha256() -> None:
    """CI guard: res/qemu-pins.yaml image digests must be pinned."""
    pins_path = find_workspace_root() / "res" / "qemu-pins.yaml"
    data = yaml.safe_load(pins_path.read_text()) or {}
    images = data.get("images") or {}
    pending = [
        key
        for key, spec in images.items()
        if str(spec.get("sha256", "")).startswith("pending")
    ]
    assert not pending, f"unpinned image sha256 in qemu-pins.yaml: {pending}"


def test_load_pins_parses_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pins_dir = tmp_path / "res"
    pins_dir.mkdir()
    (pins_dir / "qemu-pins.yaml").write_text(
        yaml.dump(
            {
                "images": {
                    "ubuntu_2404_arm64": {
                        "url": "https://example.com/img",
                        "sha256": _TEST_SHA,
                    }
                }
            }
        )
    )
    monkeypatch.setattr(qi, "find_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(qi, "_PINS_PATH", Path("res/qemu-pins.yaml"))
    pins = qi._load_pins()
    assert pins.images["ubuntu_2404_arm64"].url == "https://example.com/img"
