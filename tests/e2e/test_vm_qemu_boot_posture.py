"""E2E: rehearse the boot-posture kernel cmdline in a disposable QEMU guest.

Applies the same grub transformation the operator will apply to the host,
restarts the guest, and asserts the guest returns with the bpf LSM active and
lockdown in integrity mode. This is the pre-flight for the host edit: a wrong
cmdline fails the guest boot here, not the operator's host.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.e2e.qemu_availability import qemu_e2e_available
from tests.e2e.qemu_cleanup import _VMS_DIR, QemuTracker, run_vm_create
from tests.e2e.qemu_host_isolation import assert_host_git_unchanged, snapshot_host_git

_GUARD_CONFIG = Path("workspace/config/vm-guard-qemu.yaml")
_GUEST_SCRIPT_REL = "scripts/e2e/workspace-guard-boot-posture-guest.sh"
_GUEST_SCRIPT = f"/opt/workspace/{_GUEST_SCRIPT_REL}"
_CREATE_TIMEOUT = 3600
_APPLY_TIMEOUT = 600
_BOOT_TIMEOUT = 600
_SSH_OPTS = [
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=5",
]


def _qemu_boot_posture_available() -> bool:
    return Path(_GUEST_SCRIPT_REL).is_file() and qemu_e2e_available(_GUARD_CONFIG)


def _ssh(
    port: int,
    key: Path,
    *remote: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    command = [
        "ssh",
        "-i",
        str(key),
        *_SSH_OPTS,
        "-p",
        str(port),
        "workspace@127.0.0.1",
        *remote,
    ]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr, flush=True)
        raise


def _boot_id(port: int, key: Path) -> str:
    result = _ssh(port, key, "cat", "/proc/sys/kernel/random/boot_id", timeout=30)
    return result.stdout.strip()


def _wait_boot_change(port: int, key: Path, previous: str) -> str:
    deadline = time.monotonic() + _BOOT_TIMEOUT
    saw_guest_down = False
    while time.monotonic() < deadline:
        try:
            result = _ssh(
                port,
                key,
                "cat",
                "/proc/sys/kernel/random/boot_id",
                timeout=15,
            )
        except subprocess.CalledProcessError:
            saw_guest_down = True
        else:
            current = result.stdout.strip()
            if saw_guest_down and current and current != previous:
                return current
        time.sleep(5)
    msg = f"guest did not return within {_BOOT_TIMEOUT}s"
    raise AssertionError(msg)


@pytest.mark.e2e
@pytest.mark.skipif(
    not _qemu_boot_posture_available(),
    reason="qemu, genisoimage, guard config, or guest script not available",
)
def test_vm_qemu_boot_posture_e2e_guest(qemu_tracker: QemuTracker) -> None:
    """Apply bpf LSM + lockdown in the guest, restart, verify, run guard gate."""
    before = snapshot_host_git()

    create = run_vm_create(_GUARD_CONFIG, timeout=_CREATE_TIMEOUT, tracker=qemu_tracker)
    assert create.returncode == 0, create.stderr + create.stdout

    uuid_val = qemu_tracker.uuids[-1]
    vm_dir = _VMS_DIR / uuid_val
    port = int((vm_dir / "ssh_port").read_text().strip())
    key = vm_dir / "qemu_ssh_ed25519"

    previous_boot = _boot_id(port, key)

    applied = _ssh(
        port, key, "sudo", "bash", _GUEST_SCRIPT, "apply", timeout=_APPLY_TIMEOUT
    )
    print(applied.stdout, flush=True)
    assert "APPLY: grub updated" in applied.stdout, applied.stdout + applied.stderr

    _ssh(
        port,
        key,
        "sudo",
        "systemd-run",
        "--on-active=2",
        "--unit=wpg-boot-posture",
        "systemctl",
        "reboot",
        timeout=60,
    )

    _wait_boot_change(port, key, previous_boot)

    verified = _ssh(
        port, key, "sudo", "bash", _GUEST_SCRIPT, "verify", timeout=_APPLY_TIMEOUT
    )
    print(verified.stdout, flush=True)
    assert "BOOT-POSTURE: PASS" in verified.stdout, verified.stdout + verified.stderr

    after = snapshot_host_git()
    assert_host_git_unchanged(before, after)
