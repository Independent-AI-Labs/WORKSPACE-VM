"""Subprocess helpers with explicit ``check=True`` (no silent swallow)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Any


def _completed_from_error(
    exc: subprocess.CalledProcessError,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        exc.cmd,
        exc.returncode,
        exc.stdout or "",
        exc.stderr or "",
    )


def run(cmd: Sequence[str] | str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run *cmd*; raise ``CalledProcessError`` on non-zero exit."""
    return subprocess.run(cmd, check=True, **kwargs)


def run_result(
    cmd: Sequence[str] | str,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run *cmd*; return ``CompletedProcess`` (caller inspects ``returncode``)."""
    try:
        return run(cmd, **kwargs)
    except subprocess.CalledProcessError as exc:
        return _completed_from_error(exc)


def run_ok(cmd: Sequence[str] | str, **kwargs: Any) -> bool:
    """Return True when *cmd* exits zero and output passes optional rejection."""
    reject_in_output = kwargs.pop("reject_in_output", None)
    try:
        result = run(cmd, **kwargs)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    if reject_in_output is None:
        return True
    combined = f"{result.stdout}\n{result.stderr}".lower()
    return reject_in_output.lower() not in combined
