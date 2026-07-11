"""Resolve QEMU binaries and firmware from the platform boot directory."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from workspace.cli.vpn_core import boot_name, find_workspace_root

_GUEST_BIN = {
    "aarch64": "qemu-system-aarch64",
    "x86_64": "qemu-system-x86_64",
}


class _QemuBinaryNotFoundError(FileNotFoundError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"{name} not found; run: make install-qemu "
            f"(or workspace/scripts/bootstrap/bootstrap_qemu.sh)"
        )


def workspace_boot_dir(root: Path | None = None) -> Path:
    ws = root or find_workspace_root()
    return ws / boot_name()


def resolve_qemu_system(guest_arch: str, *, allow_path: bool = True) -> Path:
    binary_name = _GUEST_BIN.get(guest_arch)
    if binary_name is None:
        msg = f"unsupported guest_arch: {guest_arch}"
        raise ValueError(msg)
    boot_bin = workspace_boot_dir() / "bin" / binary_name
    if boot_bin.is_file():
        return boot_bin
    if allow_path:
        found = shutil.which(binary_name)
        if found:
            print(
                f"vm: WARNING: using PATH {binary_name} "
                f"(boot-dir missing; run make install-qemu)",
                file=sys.stderr,
            )
            return Path(found)
    raise _QemuBinaryNotFoundError(binary_name)


def resolve_qemu_img(*, allow_path: bool = True) -> Path:
    boot_bin = workspace_boot_dir() / "bin" / "qemu-img"
    if boot_bin.is_file():
        return boot_bin
    if allow_path:
        found = shutil.which("qemu-img")
        if found:
            print(
                "vm: WARNING: using PATH qemu-img "
                "(boot-dir missing; run make install-qemu)",
                file=sys.stderr,
            )
            return Path(found)
    raise _QemuBinaryNotFoundError("qemu-img")


def resolve_aarch64_firmware() -> Path | None:
    bundled = workspace_boot_dir() / "share" / "qemu" / "firmware" / "QEMU_EFI.fd"
    if bundled.is_file():
        return bundled
    if platform.system() == "Darwin":
        brew = shutil.which("brew")
        if brew:
            prefix = Path(
                subprocess.check_output([brew, "--prefix", "qemu"], text=True).strip()
            )
            candidate = prefix / "share" / "qemu" / "edk2-aarch64-code.fd"
            if candidate.is_file():
                return candidate
    else:
        distro = Path("/usr/share/qemu-efi-aarch64/QEMU_EFI.fd")
        if distro.is_file():
            return distro
    return None


def probe_accel(qemu_bin: Path, accel: str) -> bool:
    try:
        subprocess.run(
            [
                str(qemu_bin),
                "-accel",
                accel,
                "-machine",
                "none",
                "-display",
                "none",
            ],
            capture_output=True,
            timeout=10,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return True


def resolve_accel(requested: str, qemu_bin: Path) -> str:
    if requested != "auto":
        return requested
    system = platform.system()
    if system == "Linux":
        return "kvm" if probe_accel(qemu_bin, "kvm") else "tcg"
    if system == "Darwin":
        return "hvf" if probe_accel(qemu_bin, "hvf") else "tcg"
    if system == "Windows":
        return "whpx" if probe_accel(qemu_bin, "whpx") else "tcg"
    return "tcg"
