"""QEMU workspace sync over SSH."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from workspace.cli.vm_core import _VMS_DIR
from workspace.cli.vm_lifecycle import load_vm_config
from workspace.types.vm import VM_INSTALL_ROOT

_SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"
)


def sync(uuid: str) -> None:
    cfg = load_vm_config(uuid)
    if cfg.isolation.backend != "qemu":
        msg = f"vm: qemu sync requires the qemu backend: {uuid}"
        raise ValueError(msg)
    if not cfg.sync:
        print(f"vm: no sync rules configured for VM '{uuid}'")
        return
    vm_dir = _VMS_DIR / uuid
    port = (vm_dir / "ssh_port").read_text().strip()
    key = vm_dir / "qemu_ssh_ed25519"
    ssh = f"ssh -i {key} {_SSH_OPTS} -p {port}"
    remote = f"workspace@127.0.0.1:{VM_INSTALL_ROOT}/"
    synced = 0
    for entry in cfg.sync:
        source = Path(os.path.expanduser(entry.dir))
        if not source.is_dir():
            print(f"vm: sync: source directory '{source}' not found")
            continue
        if _escapes(source):
            msg = f"vm: sync: source escapes workspace: {source}"
            raise ValueError(msg)
        command = ["rsync", "-az", "-e", ssh]
        for pattern in entry.exclude:
            command.extend(["--exclude", pattern])
        if entry.strategy == "overwrite":
            command.append("--delete")
        elif entry.strategy == "skip":
            command.append("--ignore-existing")
        command.extend([f"{source}/", remote])
        subprocess.run(command, check=True)
        synced += 1
    label = "directory" if synced == 1 else "directories"
    print(f"vm: synced {synced} {label} to VM '{uuid}'")


def _escapes(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return resolved == Path(resolved.anchor)
