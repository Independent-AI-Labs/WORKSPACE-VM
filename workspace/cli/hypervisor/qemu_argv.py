"""Build QEMU argv lists: pure functions, no subprocess (GPL-safe orchestration)."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from workspace.types.vm import VMConfig


class QemuLaunchContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    qemu_bin: Path
    accel: str
    ssh_port: int
    firmware: Path | None = None


_MEM_RE = re.compile(r"^(\d+)([gGmM])?$")


def parse_memory_mb(memory: str) -> int:
    match = _MEM_RE.match(memory.strip())
    if not match:
        msg = f"invalid memory value: {memory!r}"
        raise ValueError(msg)
    amount = int(match.group(1))
    unit = (match.group(2) or "g").lower()
    if unit == "g":
        return amount * 1024
    return amount


def build_qemu_argv(
    *,
    cfg: VMConfig,
    vm_dir: Path,
    launch: QemuLaunchContext,
) -> list[str]:
    q = cfg.isolation.qemu
    memory_mb = parse_memory_mb(cfg.resources.memory)
    disk = vm_dir / "disk.qcow2"
    seed = vm_dir / "cloud-init" / "seed.img"
    pidfile = vm_dir / "qemu.pid"
    log_file = vm_dir / "qemu.log"
    cpu = "host" if launch.accel == "kvm" else "max"

    argv: list[str] = [
        str(launch.qemu_bin),
        "-accel",
        launch.accel,
        "-cpu",
        cpu,
    ]

    if q.guest_arch == "aarch64":
        argv.extend(["-machine", "virt,gic-version=3,acpi=on"])
        if launch.firmware is not None:
            argv.extend(["-bios", str(launch.firmware)])
    else:
        argv.extend(["-machine", "q35"])

    argv.extend(
        [
            "-m",
            str(memory_mb),
            "-smp",
            str(cfg.resources.cpus),
            "-drive",
            f"file={disk},if=virtio,format=qcow2",
            "-drive",
            f"file={seed},format=raw,if=virtio",
            "-netdev",
            f"user,id=net0,hostfwd=tcp:127.0.0.1:{launch.ssh_port}-:22",
            "-device",
            "virtio-net-pci,netdev=net0",
            "-device",
            "virtio-rng-pci",
            "-nographic",
            "-pidfile",
            str(pidfile),
            "-daemonize",
            "-D",
            str(log_file),
        ]
    )
    return argv
