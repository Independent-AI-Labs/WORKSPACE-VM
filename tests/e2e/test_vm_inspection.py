"""E2E tests for vm list/status/config/logs."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import vm_cmd

pytestmark = pytest.mark.e2e


class TestVMList:
    def test_list_shows_running_vm(self, test_vm: str) -> None:
        list_result = vm_cmd("list")
        assert list_result.returncode == 0
        assert test_vm in list_result.stdout

    def test_list_shows_stopped_vm(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        list_result = vm_cmd("list")
        assert test_vm in list_result.stdout

    def test_list_empty_ok(self) -> None:
        result = vm_cmd("list")
        assert result.returncode == 0

    def test_list_uses_table_format(self) -> None:
        result = vm_cmd("list")
        assert result.returncode == 0
        assert "NAMES" in result.stdout or result.stdout.strip() == ""


class TestVMStatus:
    def test_status_running_vm(self, test_vm: str) -> None:
        status_result = vm_cmd("status", test_vm)
        assert status_result.returncode == 0

    def test_status_stopped_vm(self, test_vm: str) -> None:
        vm_cmd("stop", test_vm)
        status_result = vm_cmd("status", test_vm)
        assert status_result.returncode == 0

    def test_status_nonexistent_vm(self) -> None:
        result = vm_cmd("status", "nonexistent-uuid-12345")
        assert result.returncode != 0


class TestVMConfig:
    def test_config_prints_stored_yaml(self, test_vm: str) -> None:
        config_result = vm_cmd("config", test_vm)
        assert config_result.returncode == 0
        assert "components" in config_result.stdout

    def test_config_nonexistent_vm(self) -> None:
        result = vm_cmd("config", "nonexistent-uuid-12345")
        assert result.returncode != 0


class TestVMLogs:
    def test_logs_returns_output(self, test_vm: str) -> None:
        logs_result = vm_cmd("logs", test_vm)
        assert logs_result.returncode == 0

    def test_logs_nonexistent_vm(self) -> None:
        result = vm_cmd("logs", "nonexistent-uuid-12345")
        assert result.returncode != 0
