"""E2E tests for vm exec/cert/sync."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import vm_cmd

pytestmark = pytest.mark.e2e


class TestVMExec:
    def test_exec_returns_output(self, test_vm: str) -> None:
        exec_result = vm_cmd("exec", test_vm, "-", "echo", "hello-world")
        assert "hello-world" in exec_result.stdout

    def test_exec_exit_code_zero(self, test_vm: str) -> None:
        exec_result = vm_cmd("exec", test_vm, "-", "true")
        assert exec_result.returncode == 0

    def test_exec_exit_code_nonzero(self, test_vm: str) -> None:
        exec_result = vm_cmd("exec", test_vm, "-", "false")
        assert exec_result.returncode == 1

    def test_exec_with_args(self, test_vm: str) -> None:
        exec_result = vm_cmd("exec", test_vm, "-", "ls", "/")
        assert exec_result.returncode == 0

    def test_exec_nonexistent_vm(self) -> None:
        result = vm_cmd("exec", "nonexistent-uuid-12345", "-", "echo", "hi")
        assert result.returncode != 0


class TestVMCert:
    def test_cert_prints_paths(self, test_vm: str) -> None:
        cert_result = vm_cmd("cert", test_vm)
        assert cert_result.returncode == 0
        assert "client.crt" in cert_result.stdout

    def test_cert_nonexistent_vm(self) -> None:
        result = vm_cmd("cert", "nonexistent-uuid-12345")
        assert result.returncode != 0


class TestVMSync:
    def test_sync_no_rules(self, test_vm: str) -> None:
        sync_result = vm_cmd("sync", test_vm)
        assert sync_result.returncode == 0

    def test_sync_nonexistent_vm(self) -> None:
        result = vm_cmd("sync", "nonexistent-uuid-12345")
        assert result.returncode != 0
