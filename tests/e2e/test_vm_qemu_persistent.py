"""E2E: persistent QEMU lifecycle, rebuild, snapshot, export, and import."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from tests.e2e.qemu_availability import qemu_e2e_available
from tests.e2e.qemu_cleanup import _VMS_DIR, parse_vm_uuid
from workspace.cli import process as proc
from workspace.cli import vm_snapshots
from workspace.cli.hypervisor.qemu_backend import QemuBackend

_CONFIG = Path("workspace/config/vm-poc-qemu.yaml")
_TIMEOUT = 3600
_MARKER = "$HOME/persistent-marker.txt"


def _create() -> str:
    env = {**os.environ, "WORKSPACE_VM_MODE": "persistent"}
    result = proc.run_result(
        [
            sys.executable,
            "-m",
            "workspace.cli.vm_main",
            "create",
            str(_CONFIG),
        ],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        env=env,
    )
    uuid = parse_vm_uuid(result.stdout)
    assert uuid, result.stderr + result.stdout
    return uuid


def _purge(uuid: str) -> None:
    result = proc.run_result(
        [
            sys.executable,
            "-m",
            "workspace.cli.vm_main",
            "delete",
            uuid,
            "--purge",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.e2e
@pytest.mark.skipif(
    not qemu_e2e_available(_CONFIG),
    reason="qemu or genisoimage not installed",
)
def test_vm_qemu_persistent_lifecycle(tmp_path: Path) -> None:
    uuid = _create()
    backend = QemuBackend()
    imported = ""
    try:
        command = shlex.quote(f"echo keep > {_MARKER}")
        created = backend.exec(uuid, ["bash", "-c", command])
        assert created.returncode == 0, created.stderr

        backend.stop(uuid)
        backend.start(uuid)
        survived = backend.exec(uuid, ["bash", "-c", f"cat {_MARKER}"])
        assert survived.stdout.strip() == "keep", survived.stderr

        vm_snapshots.snapshot_create(uuid, "e2e")
        listed = subprocess.run(
            [
                sys.executable,
                "-m",
                "workspace.cli.vm_main",
                "snapshot",
                uuid,
                "list",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert listed.returncode == 0, listed.stderr
        vm_snapshots.snapshot_delete(uuid, "e2e")

        backend.rebuild(uuid)
        rebuilt = backend.exec(uuid, ["bash", "-c", f"cat {_MARKER}"])
        assert rebuilt.stdout.strip() == "keep", rebuilt.stderr

        bundle = tmp_path / "bundle"
        vm_snapshots.export_vm(uuid, bundle)
        imported = vm_snapshots.import_vm(bundle)
        backend.start(imported)
        restored = backend.exec(imported, ["bash", "-c", f"cat {_MARKER}"])
        assert restored.stdout.strip() == "keep", restored.stderr
    finally:
        if imported:
            _purge(imported)
        _purge(uuid)
        assert not (_VMS_DIR / uuid).exists()
