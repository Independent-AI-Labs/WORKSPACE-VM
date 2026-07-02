"""E2E tests for vm start/stop/kill/delete/resume."""

from __future__ import annotations

import subprocess

import pytest

from tests.e2e.conftest import _VMS_DIR, vm_cmd

pytestmark = pytest.mark.e2e


class TestVMStartStop:
    def test_stop_running_vm(self, test_vm: str) -> None:
        stop_result = vm_cmd("stop", test_vm)
        assert stop_result.returncode == 0
        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Status}}", test_vm],
            capture_output=True,
            text=True,
            check=True,
        )
        assert inspect.stdout.strip() == "exited"
        assert not (_VMS_DIR / test_vm / "pid").exists()

    def test_start_stopped_vm(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        start_result = vm_cmd("start", test_vm)
        assert start_result.returncode == 0
        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Status}}", test_vm],
            capture_output=True,
            text=True,
            check=True,
        )
        assert inspect.stdout.strip() == "running"
        assert (_VMS_DIR / test_vm / "pid").exists()

    def test_stop_idempotent(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        result = vm_cmd("stop", test_vm)
        assert result.returncode == 0

    def test_start_idempotent(self, test_vm: str) -> None:
        result = vm_cmd("start", test_vm)
        assert result.returncode == 0

    def test_resume_alias_equals_start(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        resume_result = vm_cmd("resume", test_vm)
        assert resume_result.returncode == 0
        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Status}}", test_vm],
            capture_output=True,
            text=True,
            check=True,
        )
        assert inspect.stdout.strip() == "running"

    def test_stop_nonexistent_vm(self) -> None:
        result = vm_cmd("stop", "nonexistent-uuid-12345")
        assert result.returncode != 0

    def test_start_nonexistent_vm(self) -> None:
        result = vm_cmd("start", "nonexistent-uuid-12345")
        assert result.returncode != 0


class TestVMKill:
    def test_kill_by_pid(self, test_vm: str) -> None:
        kill_result = vm_cmd("kill", test_vm)
        assert kill_result.returncode == 0
        assert "SIGKILL" in kill_result.stdout
        inspect = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Status}}", test_vm],
            capture_output=True,
            text=True,
            check=True,
        )
        assert inspect.stdout.strip() in ("exited", "stopped")

    def test_kill_nonexistent_vm(self) -> None:
        result = vm_cmd("kill", "nonexistent-uuid-12345")
        assert result.returncode != 0


class TestVMDelete:
    def test_delete_removes_container(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        delete_result = vm_cmd("delete", test_vm)
        assert delete_result.returncode == 0
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.run(
                ["podman", "inspect", test_vm],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_delete_preserves_volumes_by_default(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        vm_cmd("delete", test_vm)
        for suffix in ("workspace", "transcripts", "cache"):
            vol_result = subprocess.run(
                ["podman", "volume", "exists", f"{test_vm}-{suffix}"],
                capture_output=True,
                check=True,
            )
            assert vol_result.returncode == 0

    def test_delete_with_purge(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        delete_result = vm_cmd("delete", test_vm, "--purge")
        assert delete_result.returncode == 0
        for suffix in ("workspace", "transcripts", "cache"):
            with pytest.raises(subprocess.CalledProcessError):
                subprocess.run(
                    ["podman", "volume", "exists", f"{test_vm}-{suffix}"],
                    capture_output=True,
                    check=True,
                )

    def test_delete_running_vm(self, test_vm: str) -> None:
        delete_result = vm_cmd("delete", test_vm)
        assert delete_result.returncode == 0
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.run(
                ["podman", "inspect", test_vm],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_delete_nonexistent_vm(self) -> None:
        result = vm_cmd("delete", "nonexistent-uuid-12345")
        assert result.returncode != 0
