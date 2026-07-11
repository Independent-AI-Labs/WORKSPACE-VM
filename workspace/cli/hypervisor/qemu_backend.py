"""QEMU isolation backend: subprocess-only, no libqemu linkage."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

from workspace.cli.hypervisor.qemu_argv import QemuLaunchContext, build_qemu_argv
from workspace.cli.hypervisor.qemu_images import prepare_vm_storage
from workspace.cli.hypervisor.qemu_resolve import (
    resolve_aarch64_firmware,
    resolve_accel,
    resolve_qemu_system,
)
from workspace.cli.vm_core import _VMS_DIR, _generate_password
from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7

_HEALTH_TIMEOUT = 120
_HEALTH_POLL = 2
_STOP_TIMEOUT = 30


class QemuBackend:
    """Full Linux guest via qemu-system-*."""

    def backend_name(self) -> str:
        return "qemu"

    def create(self, config_path: str, cfg: VMConfig) -> None:
        uuid_str = uuid7()
        vm_dir = _VMS_DIR / uuid_str
        vm_dir.mkdir(parents=True, exist_ok=True)

        password = _generate_password()
        (vm_dir / "password").write_text(password)
        shutil.copy2(config_path, vm_dir / "vm.yaml")

        q = cfg.isolation.qemu
        qemu_bin = resolve_qemu_system(q.guest_arch)
        accel = resolve_accel(q.accel, qemu_bin)
        firmware = resolve_aarch64_firmware() if q.guest_arch == "aarch64" else None
        if q.guest_arch == "aarch64" and firmware is None:
            print(
                "vm: WARNING: EDK2 firmware not found; guest may not boot "
                "(run make install-qemu)",
                file=sys.stderr,
            )

        ssh_port = int(prepare_vm_storage(cfg, vm_dir))
        launch = QemuLaunchContext(
            qemu_bin=qemu_bin,
            accel=accel,
            ssh_port=ssh_port,
            firmware=firmware,
        )
        argv = build_qemu_argv(cfg=cfg, vm_dir=vm_dir, launch=launch)
        subprocess.run(argv, check=True)
        _wait_ssh(int(ssh_port), vm_dir / "qemu_ssh_ed25519")

        print(f"VM {uuid_str} created (qemu)")
        print(f"  UUID:     {uuid_str}")
        print(f"  Backend:  qemu ({accel})")
        ssh_key = vm_dir / "qemu_ssh_ed25519"
        print(f"  SSH:      ssh -i {ssh_key} -p {ssh_port} workspace@127.0.0.1")

    def start(self, uuid: str) -> None:
        vm_dir = _VMS_DIR / uuid
        vm_yaml = vm_dir / "vm.yaml"
        if not vm_yaml.is_file():
            msg = f"vm: no vm.yaml found for VM '{uuid}'"
            raise FileNotFoundError(msg)
        cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
        if self.status(uuid).get("state") == "running":
            return

        q = cfg.isolation.qemu
        qemu_bin = resolve_qemu_system(q.guest_arch)
        accel = resolve_accel(q.accel, qemu_bin)
        firmware = resolve_aarch64_firmware() if q.guest_arch == "aarch64" else None
        ssh_port = int((vm_dir / "ssh_port").read_text().strip())
        launch = QemuLaunchContext(
            qemu_bin=qemu_bin,
            accel=accel,
            ssh_port=ssh_port,
            firmware=firmware,
        )
        argv = build_qemu_argv(cfg=cfg, vm_dir=vm_dir, launch=launch)
        subprocess.run(argv, check=True)
        _wait_ssh(ssh_port, vm_dir / "qemu_ssh_ed25519")

    def stop(self, uuid: str) -> None:
        pid_file = _VMS_DIR / uuid / "qemu.pid"
        if not pid_file.is_file():
            return
        pid = int(pid_file.read_text().strip())
        try:
            subprocess.run(
                ["kill", "-TERM", str(pid)],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                sys.stderr.write(exc.stderr)
        deadline = time.monotonic() + _STOP_TIMEOUT
        while time.monotonic() < deadline:
            if not _process_alive(pid):
                pid_file.unlink(missing_ok=True)
                return
            time.sleep(1)
        try:
            subprocess.run(
                ["kill", "-KILL", str(pid)],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                sys.stderr.write(exc.stderr)
        pid_file.unlink(missing_ok=True)

    def destroy(self, uuid: str, *, purge: bool = False) -> None:
        self.stop(uuid)
        vm_dir = _VMS_DIR / uuid
        if vm_dir.is_dir():
            shutil.rmtree(vm_dir)

    def exec(self, uuid: str, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        host, port = self.ssh_endpoint(uuid)
        key = _VMS_DIR / uuid / "qemu_ssh_ed25519"
        return subprocess.run(
            [
                "ssh",
                "-i",
                str(key),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-p",
                str(port),
                f"workspace@{host}",
                *cmd,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def ssh_endpoint(self, uuid: str) -> tuple[str, int]:
        port_file = _VMS_DIR / uuid / "ssh_port"
        return "127.0.0.1", int(port_file.read_text().strip())

    def status(self, uuid: str) -> dict[str, str]:
        pid_file = _VMS_DIR / uuid / "qemu.pid"
        if not pid_file.is_file():
            return {"state": "unknown", "backend": "qemu"}
        pid = pid_file.read_text().strip()
        if _process_alive(int(pid)):
            return {"state": "running", "backend": "qemu", "pid": pid}
        return {"state": "stopped", "backend": "qemu"}


def _process_alive(pid: int) -> bool:
    try:
        subprocess.run(["kill", "-0", str(pid)], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        return False
    return True


def _probe_ssh(port: int, identity: Path) -> bool:
    try:
        subprocess.run(
            [
                "ssh",
                "-i",
                str(identity),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "ConnectTimeout=3",
                "-p",
                str(port),
                "workspace@127.0.0.1",
                "echo",
                "ok",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def _wait_ssh(port: int, identity: Path) -> None:
    deadline = time.monotonic() + _HEALTH_TIMEOUT
    while time.monotonic() < deadline:
        if _probe_ssh(port, identity):
            return
        time.sleep(_HEALTH_POLL)
    print("vm: WARNING: SSH health check timed out", file=sys.stderr)
