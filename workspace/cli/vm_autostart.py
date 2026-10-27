"""Systemd user autostart for persistent QEMU VMs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workspace.cli.hypervisor.qemu_state import is_persistent
from workspace.cli.vm_core import _VMS_DIR
from workspace.cli.vpn_core import find_workspace_root

_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


def _unit_name(uuid: str) -> str:
    return f"workspace-vm-{uuid}.service"


def _unit_path(uuid: str) -> Path:
    return _UNIT_DIR / _unit_name(uuid)


def _unit_body(uuid: str) -> str:
    root = find_workspace_root()
    vm_dir = _VMS_DIR / uuid
    environment = f"Environment=WS_VM_DIR={vm_dir.parent}\n"
    return (
        "[Unit]\n"
        f"Description=WORKSPACE-VM {uuid}\n"
        "After=default.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "RemainAfterExit=yes\n"
        f"WorkingDirectory={root}\n"
        f"{environment}"
        f"ExecStart={root}/workspace/scripts/bin/vm start {uuid}\n"
        f"ExecStop={root}/workspace/scripts/bin/vm stop {uuid}\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _systemctl(*args: str) -> None:
    try:
        subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        msg = f"vm: systemd user service unavailable for {args}"
        raise RuntimeError(msg) from exc


def enable(uuid: str) -> None:
    vm_dir = _VMS_DIR / uuid
    if not (vm_dir / "vm.yaml").is_file():
        msg = f"vm: no vm.yaml found for VM '{uuid}'"
        raise FileNotFoundError(msg)
    if not is_persistent(vm_dir):
        msg = f"vm: autostart requires a persistent VM: {uuid}"
        raise ValueError(msg)
    require_systemd()
    _UNIT_DIR.mkdir(parents=True, exist_ok=True)
    _unit_path(uuid).write_text(_unit_body(uuid))
    _unit_path(uuid).chmod(0o644)
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", _unit_name(uuid))
    print(f"VM {uuid} autostart enabled")


def disable(uuid: str) -> None:
    unit = _unit_name(uuid)
    path = _unit_path(uuid)
    if not path.is_file():
        msg = f"vm: autostart is not enabled for {uuid}"
        raise FileNotFoundError(msg)
    _systemctl("disable", "--now", unit)
    path.unlink()
    _systemctl("daemon-reload")
    print(f"VM {uuid} autostart disabled")


def _env_has_systemd() -> bool:
    return "XDG_RUNTIME_DIR" in os.environ


def require_systemd() -> None:
    if not _env_has_systemd():
        msg = "vm: XDG_RUNTIME_DIR is not set; systemd user services are unavailable"
        sys.stderr.write(msg + "\n")
        raise RuntimeError(msg)
