"""VM file sync — rsync host directories into the VM workspace volume."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

from workspace.cli.vm_core import _VMS_DIR, _podman
from workspace.types.vm import VMConfig


def sync(uuid_str: str) -> None:
    """File sync from host to VM workspace volume per config.sync rules."""
    vm_yaml = _VMS_DIR / uuid_str / "vm.yaml"
    if not vm_yaml.exists():
        print(f"vm: no vm.yaml found for VM '{uuid_str}'", file=sys.stderr)
        sys.exit(1)
    cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
    if not cfg.sync:
        print(f"vm: no sync rules configured for VM '{uuid_str}'")
        return
    try:
        mountpoint = _podman(
            "volume",
            "inspect",
            "-f",
            "{{.Mountpoint}}",
            f"{uuid_str}-workspace",
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(
            f"vm: cannot find workspace volume for VM '{uuid_str}'",
            file=sys.stderr,
        )
        sys.exit(1)
    synced = 0
    for entry in cfg.sync:
        src_dir = Path(os.path.expanduser(entry.dir))
        if not src_dir.is_dir():
            print(f"vm: sync: source directory '{src_dir}' not found, skipping")
            continue
        exclude_args: list[str] = []
        for pattern in entry.exclude:
            exclude_args.extend(["--exclude", pattern])
        rsync_cmd: list[str] = ["rsync", "-a", *exclude_args]
        if entry.strategy == "overwrite":
            rsync_cmd.append("--delete")
        subprocess.run(
            [*rsync_cmd, f"{src_dir}/", str(mountpoint)],
            check=True,
        )
        synced += 1
    label = "directory" if synced == 1 else "directories"
    print(f"vm: synced {synced} {label} to VM '{uuid_str}'")


def _remove_hosts_entry(uuid_str: str) -> None:
    """Remove /etc/hosts entry for a VM."""
    hosts_file = Path("/etc/hosts")
    if not hosts_file.exists():
        return
    content = hosts_file.read_text()
    if f"{uuid_str}.vm.local" not in content:
        return
    new_lines = [
        line for line in content.splitlines() if f"{uuid_str}.vm.local" not in line
    ]
    try:
        hosts_file.write_text("\n".join(new_lines) + "\n")
    except PermissionError:
        sys.stderr.write(
            f"vm: WARNING: could not write /etc/hosts for {uuid_str} (try sudo)\n"
        )
