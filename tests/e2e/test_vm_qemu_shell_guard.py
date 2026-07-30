"""E2E: WORKSPACE-GUARD shell guard authoritative gate inside QEMU guest."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.e2e.qemu_availability import qemu_e2e_available
from tests.e2e.qemu_cleanup import QemuTracker, run_vm_create
from tests.e2e.qemu_host_isolation import assert_host_git_unchanged, snapshot_host_git

_GUARD_CONFIG = Path("workspace/config/vm-guard-qemu.yaml")
_E2E_GUEST = Path("projects/WORKSPACE-GUARD/scripts/qemu/e2e-shell-guard-guest.sh")
_CREATE_TIMEOUT = 600
_GUARD_TIMEOUT = 600


def _run_streaming(cmd: list[str], timeout: int) -> tuple[int, str]:
    """Run cmd, stream output live to stdout, return (returncode, full output)."""
    collected: list[str] = []
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as proc_handle:
        deadline = time.monotonic() + timeout
        assert proc_handle.stdout is not None
        for line in proc_handle.stdout:
            collected.append(line)
            print(line, end="", flush=True)
            if time.monotonic() > deadline:
                proc_handle.kill()
                proc_handle.wait()
                return 124, "".join(collected)
        return proc_handle.wait(), "".join(collected)


def _qemu_shell_guard_available() -> bool:
    return _E2E_GUEST.is_file() and qemu_e2e_available(_GUARD_CONFIG)


@pytest.mark.e2e
@pytest.mark.skipif(
    not _qemu_shell_guard_available(),
    reason="qemu, genisoimage, or guard config not available",
)
def test_vm_qemu_shell_guard_e2e_guest(qemu_tracker: QemuTracker) -> None:
    """Provision guard VM, run e2e-shell-guard-guest.sh, verify host unchanged."""
    before = snapshot_host_git()

    print("=== vm create ===", flush=True)
    create = run_vm_create(_GUARD_CONFIG, timeout=_CREATE_TIMEOUT, tracker=qemu_tracker)
    sys.stdout.write(create.stdout + create.stderr)
    sys.stdout.flush()
    assert create.returncode == 0, create.stderr + create.stdout

    uuid = qemu_tracker.uuids[-1]
    vm_dir = Path(".vms") / uuid
    port = int((vm_dir / "ssh_port").read_text().strip())
    key = vm_dir / "qemu_ssh_ed25519"
    ssh_base = [
        "-i",
        str(key),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
    ]

    prebuilt = Path(
        "projects/WORKSPACE-GUARD/target/agent/release/workspace-shell-guard"
    )
    assert prebuilt.is_file(), (
        "build first: cargo build --release --bin workspace-shell-guard"
        f" (missing {prebuilt})"
    )
    print("=== ship prebuilt guard binary ===", flush=True)
    rc, scp_out = _run_streaming(
        [
            "scp",
            *ssh_base,
            "-P",
            str(port),
            str(prebuilt),
            "workspace@127.0.0.1:/tmp/shg-prebuilt",
        ],
        timeout=120,
    )
    assert rc == 0, scp_out

    print("=== guest battery ===", flush=True)
    rc, guard_out = _run_streaming(
        [
            "ssh",
            *ssh_base,
            "-p",
            str(port),
            "workspace@127.0.0.1",
            "sudo",
            "SHG_PREBUILT=/tmp/shg-prebuilt",
            "bash",
            "/opt/workspace/projects/WORKSPACE-GUARD/scripts/qemu/e2e-shell-guard-guest.sh",
        ],
        timeout=_GUARD_TIMEOUT,
    )
    assert rc == 0, guard_out
    assert "make install-shell-guard applied" in guard_out, guard_out
    assert "guard hash matches release build" in guard_out, guard_out
    assert "installed-workspace: benign -c passes" in guard_out, guard_out
    assert "PASS:" in guard_out, guard_out

    after = snapshot_host_git()
    assert_host_git_unchanged(before, after)
