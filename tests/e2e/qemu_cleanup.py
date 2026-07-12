"""QEMU E2E cleanup: guaranteed VM teardown and orphan reclamation."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from workspace.cli import process as proc
from workspace.cli.hypervisor.qemu_backend import QemuBackend

_VMS_DIR = Path(".vms")
_BASE_CACHE = _VMS_DIR / "_base"
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def parse_vm_uuid(stdout: str) -> str:
    """Extract VM UUID from vm create stdout."""
    for line in stdout.splitlines():
        if line.startswith("VM ") and "created" in line:
            return line.split()[1]
        if line.startswith("  UUID:"):
            return line.split()[1].strip()
    return ""


def _keep_vm_on_exit() -> bool:
    return os.environ.get("QEMU_E2E_KEEP_VM", "0") == "1"


class QemuTracker:
    """Track QEMU VMs and destroy them on teardown (pass or fail)."""

    def __init__(self) -> None:
        self.uuids: list[str] = []

    def register(self, uuid_val: str) -> None:
        if uuid_val and uuid_val not in self.uuids:
            self.uuids.append(uuid_val)

    def destroy(self, uuid_val: str) -> None:
        if _keep_vm_on_exit():
            print(
                f"QEMU_E2E_KEEP_VM=1: leaving VM {uuid_val} under {_VMS_DIR}",
                file=sys.stderr,
            )
            return
        backend = QemuBackend()
        try:
            backend.destroy(uuid_val)
        except OSError as exc:
            print(
                f"WARNING: qemu destroy failed for {uuid_val}: {exc}", file=sys.stderr
            )
        vm_path = _VMS_DIR / uuid_val
        if vm_path.is_dir():
            shutil.rmtree(vm_path, ignore_errors=True)

    def cleanup(self) -> None:
        for uuid_val in list(self.uuids):
            self.destroy(uuid_val)


def destroy_qemu_vm(uuid_val: str) -> None:
    """Destroy one QEMU VM and remove its .vms/<uuid>/ directory."""
    tracker = QemuTracker()
    tracker.register(uuid_val)
    tracker.destroy(uuid_val)


def _is_qemu_vm_dir(path: Path) -> bool:
    if not path.is_dir() or path.name == "_base":
        return False
    if not _UUID_RE.match(path.name):
        return False
    return (path / "vm.yaml").is_file() or (path / "qemu.pid").is_file()


def cleanup_orphan_qemu_vms(*, max_age_seconds: int = 0) -> list[str]:
    """Remove stale QEMU VM dirs under .vms/ (never touches _base/).

    When max_age_seconds > 0, only removes directories older than that age.
    """
    if not _VMS_DIR.is_dir():
        return []
    removed: list[str] = []
    now = time.time()
    for entry in sorted(_VMS_DIR.iterdir()):
        if not _is_qemu_vm_dir(entry):
            continue
        if max_age_seconds > 0:
            age = now - entry.stat().st_mtime
            if age < max_age_seconds:
                continue
        uuid_val = entry.name
        QemuTracker().destroy(uuid_val)
        removed.append(uuid_val)
    return removed


def cleanup_failed_create_artifacts(stdout: str, stderr: str) -> None:
    """Best-effort cleanup when vm create fails after allocating a UUID."""
    uuid_val = parse_vm_uuid(stdout) or parse_vm_uuid(stderr)
    if uuid_val:
        QemuTracker().destroy(uuid_val)


@contextmanager
def tracked_qemu_vm(tracker: QemuTracker, uuid_val: str) -> Iterator[str]:
    """Register a VM for cleanup for the duration of a test block."""
    tracker.register(uuid_val)
    try:
        yield uuid_val
    finally:
        tracker.destroy(uuid_val)


def run_vm_create(
    config_path: Path,
    *,
    timeout: int,
    tracker: QemuTracker,
) -> subprocess.CompletedProcess[str]:
    """Run vm create and register UUID for cleanup even on failure."""
    create = proc.run_result(
        [
            sys.executable,
            "-m",
            "workspace.cli.vm_main",
            "create",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    uuid_val = parse_vm_uuid(create.stdout)
    if uuid_val:
        tracker.register(uuid_val)
    elif create.returncode != 0:
        cleanup_failed_create_artifacts(create.stdout, create.stderr)
        cleanup_orphan_qemu_vms(max_age_seconds=0)
    return create
