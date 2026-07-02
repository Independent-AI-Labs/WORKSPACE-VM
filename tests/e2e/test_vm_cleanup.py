"""E2E tests for VM cleanup and teardown."""

from __future__ import annotations

import subprocess

import pytest

from tests.e2e.conftest import _VMS_DIR, vm_cmd

pytestmark = pytest.mark.e2e


class TestVMCleanup:
    def test_delete_removes_container(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        vm_cmd("delete", test_vm, "-purge")
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.run(
                ["podman", "inspect", test_vm],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_volume_cleanup_after_purge(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        vm_cmd("delete", test_vm, "-purge")
        for suffix in ("workspace", "transcripts", "cache"):
            with pytest.raises(subprocess.CalledProcessError):
                subprocess.run(
                    ["podman", "volume", "exists", f"{test_vm}-{suffix}"],
                    capture_output=True,
                    check=True,
                )

    def test_manual_volume_cleanup(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        vm_cmd("delete", test_vm)
        for suffix in ("workspace", "transcripts", "cache"):
            subprocess.run(
                ["podman", "volume", "rm", "-f", f"{test_vm}-{suffix}"],
                capture_output=True,
                check=True,
            )
        for suffix in ("workspace", "transcripts", "cache"):
            with pytest.raises(subprocess.CalledProcessError):
                subprocess.run(
                    ["podman", "volume", "exists", f"{test_vm}-{suffix}"],
                    capture_output=True,
                    check=True,
                )

    def test_orphan_volume_detection(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        vm_cmd("delete", test_vm)
        vol_result = subprocess.run(
            ["podman", "volume", "exists", f"{test_vm}-workspace"],
            capture_output=True,
            check=True,
        )
        assert vol_result.returncode == 0

    def test_pid_file_removed_after_stop(self, test_vm: str) -> None:
        assert (_VMS_DIR / test_vm / "pid").exists()
        vm_cmd("stop", test_vm)
        assert not (_VMS_DIR / test_vm / "pid").exists()
