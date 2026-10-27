"""Persistent QEMU VM state and process identity."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

STATE_FILE = "state.yaml"
_PS_TIMEOUT = 5


def _now() -> str:
    return datetime.now(UTC).isoformat()


class QemuState(BaseModel):
    """Durable state for one QEMU VM."""

    mode: Literal["persistent", "ephemeral"] = "persistent"
    profile: str = "none"
    created_at: str = Field(default_factory=_now)
    last_started_at: str | None = None
    last_stopped_at: str | None = None
    last_error: str | None = None
    ssh_port: int | None = None
    pid_start: str | None = None


class QemuStateError(ValueError):
    """Raised when a state file exists but cannot be validated."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"invalid state file: {path}")


def state_path(vm_dir: Path) -> Path:
    return vm_dir / STATE_FILE


def load_state(vm_dir: Path) -> QemuState | None:
    path = state_path(vm_dir)
    if not path.is_file():
        return None
    try:
        return QemuState.model_validate_json(path.read_text())
    except (OSError, ValidationError) as exc:
        raise QemuStateError(path) from exc


def ensure_state(
    vm_dir: Path,
    *,
    profile: str,
    mode: Literal["persistent", "ephemeral"],
) -> QemuState:
    current = load_state(vm_dir)
    if current is not None:
        return current
    state = QemuState(profile=profile, mode=mode)
    save_state(vm_dir, state)
    return state


def save_state(vm_dir: Path, state: QemuState) -> None:
    path = state_path(vm_dir)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(indent=2) + "\n")
    tmp.replace(path)


def mark_started(vm_dir: Path, *, ssh_port: int, pid_start: str | None) -> QemuState:
    state = _required_state(vm_dir)
    state.last_started_at = _now()
    state.last_stopped_at = None
    state.last_error = None
    state.ssh_port = ssh_port
    state.pid_start = pid_start
    save_state(vm_dir, state)
    return state


def mark_stopped(vm_dir: Path, *, error: str | None = None) -> QemuState:
    state = _required_state(vm_dir)
    state.last_stopped_at = _now()
    state.last_error = error
    state.pid_start = None
    save_state(vm_dir, state)
    return state


def mark_error(vm_dir: Path, message: str) -> QemuState:
    state = _required_state(vm_dir)
    state.last_error = message
    save_state(vm_dir, state)
    return state


def _required_state(vm_dir: Path) -> QemuState:
    state = load_state(vm_dir)
    if state is None:
        state = QemuState()
    return state


def is_persistent(vm_dir: Path) -> bool:
    state = load_state(vm_dir)
    if state is None:
        return True
    return state.mode == "persistent"


def process_identity(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=True,
            timeout=_PS_TIMEOUT,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        print(f"vm: process {pid} is gone: {detail}", file=sys.stderr)
        return None
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"vm: cannot read process identity for {pid}: {exc}", file=sys.stderr)
        return None
    value = result.stdout.strip()
    return value or None


def process_matches(pid: int, identity: str | None) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if identity is None:
        return True
    return process_identity(pid) == identity
