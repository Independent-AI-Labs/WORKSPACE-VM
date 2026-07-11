"""Guest disk images and cloud-init seeds for QemuBackend."""

from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import textwrap
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from workspace.cli.hypervisor.qemu_resolve import resolve_qemu_img
from workspace.cli.vpn_core import find_workspace_root
from workspace.types.vm import VMConfig

_VMS_BASE = Path(".vms") / "_base"
_PINS_PATH = Path("res/qemu-pins.yaml")


class QemuImagePin(BaseModel):
    url: str
    sha256: str = ""


class QemuPinsManifest(BaseModel):
    images: dict[str, QemuImagePin] = Field(default_factory=dict)


def _load_pins() -> QemuPinsManifest:
    root = find_workspace_root()
    path = root / _PINS_PATH
    if not path.is_file():
        return QemuPinsManifest()
    data = yaml.safe_load(path.read_text()) or {}
    return QemuPinsManifest.model_validate(data)


def _image_key(guest_arch: str) -> str:
    if guest_arch == "aarch64":
        return "ubuntu_2404_arm64"
    return "ubuntu_2404_x86_64"


def ensure_base_image(image_name: str, guest_arch: str) -> Path:
    base_dir = _VMS_BASE
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = base_dir / image_name
    if dest.is_file():
        return dest

    pins = _load_pins()
    key = _image_key(guest_arch)
    spec = pins.images.get(key)
    if spec is None:
        msg = f"no image pin for {key} in res/qemu-pins.yaml"
        raise FileNotFoundError(msg)

    url = spec.url
    raw = base_dir / f".download-{key}.img"
    _download_file(url, raw)
    expected = spec.sha256
    if expected and not expected.startswith("pending"):
        _verify_sha256(raw, expected)

    qemu_img = _resolve_qemu_img()
    subprocess.run(
        [str(qemu_img), "convert", "-O", "qcow2", str(raw), str(dest)],
        check=True,
    )
    raw.unlink(missing_ok=True)
    return dest


def create_overlay(base: Path, overlay: Path, disk_gb: int) -> None:
    qemu_img = _resolve_qemu_img()
    if overlay.exists():
        overlay.unlink()
    subprocess.run(
        [
            str(qemu_img),
            "create",
            "-f",
            "qcow2",
            "-b",
            str(base),
            "-F",
            "qcow2",
            str(overlay),
        ],
        check=True,
    )
    subprocess.run(
        [str(qemu_img), "resize", str(overlay), f"{disk_gb}G"],
        check=True,
    )


def write_cloud_init(vm_dir: Path, pubkey: str) -> None:
    ci = vm_dir / "cloud-init"
    ci.mkdir(parents=True, exist_ok=True)
    user_data = textwrap.dedent(
        f"""\
        #cloud-config
        users:
          - name: workspace
            sudo: ALL=(ALL) NOPASSWD:ALL
            shell: /bin/bash
            ssh_authorized_keys:
              - {pubkey.strip()}
        package_update: true
        packages:
          - openssh-server
        runcmd:
          - systemctl enable --now ssh
        """
    )
    (ci / "user-data").write_text(user_data)
    (ci / "meta-data").write_text(
        "instance-id: workspace-vm\nlocal-hostname: workspace-vm\n"
    )
    seed = ci / "seed.img"
    cloud_localds = _resolve_cloud_localds()
    subprocess.run(
        [
            str(cloud_localds),
            str(seed),
            str(ci / "user-data"),
            str(ci / "meta-data"),
        ],
        check=True,
    )


def generate_ssh_keypair(vm_dir: Path) -> tuple[Path, str]:
    key = vm_dir / "qemu_ssh_ed25519"
    if not key.is_file():
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key)],
            check=True,
        )
    pub = Path(f"{key}.pub").read_text().strip()
    return key, pub


def allocate_ssh_port(requested: int) -> int:
    if requested != 0:
        return requested
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "-fL", "--retry", "3", "-o", str(dest), url],
        check=True,
    )


def _verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        msg = f"SHA256 mismatch for {path}"
        raise ValueError(msg)


def _resolve_qemu_img() -> Path:
    return resolve_qemu_img()


def _resolve_cloud_localds() -> Path:
    found = shutil.which("cloud-localds")
    if found:
        return Path(found)
    msg = (
        "cloud-localds not found; install cloud-image-utils (apt) or cloud-utils (brew)"
    )
    raise FileNotFoundError(msg)


def prepare_vm_storage(cfg: VMConfig, vm_dir: Path) -> str:
    q = cfg.isolation.qemu
    base = ensure_base_image(q.image, q.guest_arch)
    overlay = vm_dir / "disk.qcow2"
    create_overlay(base, overlay, q.disk_gb)
    _, pub = generate_ssh_keypair(vm_dir)
    write_cloud_init(vm_dir, pub)
    port = allocate_ssh_port(q.ssh_host_port)
    (vm_dir / "ssh_port").write_text(str(port))
    return str(port)
