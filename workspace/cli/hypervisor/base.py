"""Isolation backend protocol for make vm."""

from __future__ import annotations

import subprocess
from typing import Protocol

from workspace.types.vm import VMConfig


class IsolationBackend(Protocol):
    """Hypervisor driver invoked by vm_manager."""

    def create(self, config_path: str, cfg: VMConfig) -> None: ...

    def start(self, uuid: str) -> None: ...

    def stop(self, uuid: str) -> None: ...

    def destroy(self, uuid: str, *, purge: bool = False) -> None: ...

    def exec(self, uuid: str, cmd: list[str]) -> subprocess.CompletedProcess[str]: ...

    def ssh_endpoint(self, uuid: str) -> tuple[str, int]: ...

    def status(self, uuid: str) -> dict[str, str]: ...

    def backend_name(self) -> str: ...
