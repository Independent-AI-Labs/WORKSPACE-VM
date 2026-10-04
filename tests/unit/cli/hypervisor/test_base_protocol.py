"""Unit tests for the IsolationBackend protocol surface."""

from __future__ import annotations

from workspace.cli.hypervisor.base import IsolationBackend

_EXPECTED_METHODS = (
    "create",
    "start",
    "stop",
    "destroy",
    "exec",
    "ssh_endpoint",
    "status",
    "backend_name",
)


def test_isolation_backend_declares_contract() -> None:
    for method in _EXPECTED_METHODS:
        assert hasattr(IsolationBackend, method)
