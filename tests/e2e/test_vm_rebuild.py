"""E2E tests for vm rebuild."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import vm_cmd

pytestmark = pytest.mark.e2e


class TestVMRebuild:
    def test_rebuild_nonexistent_vm(self) -> None:
        result = vm_cmd("rebuild", "nonexistent-uuid-12345")
        assert result.returncode != 0

    def test_rebuild_with_valid_vm(self, test_vm: str) -> None:
        result = vm_cmd("rebuild", test_vm)
        assert result.returncode != 0
