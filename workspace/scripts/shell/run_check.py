"""Tool health + version check executed by the extension registry.

Owns ``HealthCheckResult`` (the output type) and ``run_check`` (the call).
Extracted from ``extension_registry`` to keep that module under the
512-line cap. ``extension_registry`` re-exports both names for
back-compat; new code can import from either.
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import TYPE_CHECKING, NamedTuple

from workspace.scripts.shell.banner_log import CheckRecord

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from workspace.scripts.shell.extension_registry import CheckConfig, ExtensionEntry


MAX_CHECK_TIMEOUT = 5

# Semver core: MAJOR.MINOR.PATCH with optional -pre / +build suffix we discard.
_SEMVER_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+][0-9A-Za-z.-]+)?$")


class HealthCheckResult(NamedTuple):
    """Result of a health + version check."""

    healthy: bool
    version: str | None
    version_ok: bool | None = None
    version_reason: str | None = None


def _parse_semver(v: str) -> tuple[int, int, int] | None:
    """Parse a semver-ish string into a (major, minor, patch) tuple.

    Accepts ``1``, ``1.2``, ``1.2.3``, ``1.2.3-rc1``, and
    ``1.2.3+build``. Missing components are explicitly zero. Returns None
    for malformed input.
    """
    if not v:
        return None
    m = _SEMVER_RE.fullmatch(v)
    if not m:
        return None
    major, minor, patch = m.groups()
    return int(major), int(minor or "0"), int(patch or "0")


def _compare_semver(a: str, b: str) -> int | None:
    """Return -1/0/1 comparing versions, or None when either is invalid."""
    pa = _parse_semver(a)
    pb = _parse_semver(b)
    if pa is None or pb is None:
        return None
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def _constraint_failure_reason(
    version: str,
    min_version: str | None,
    max_version: str | None,
) -> str | None:
    """Return a constraint failure reason, or None when the version is valid."""
    if min_version:
        comparison = _compare_semver(version, min_version)
        if comparison is None:
            return f"unparseable version: {version!r}"
        if comparison < 0:
            return f"{version} < required minVersion {min_version}"
    if max_version:
        comparison = _compare_semver(version, max_version)
        if comparison is None:
            return f"unparseable version: {version!r}"
        if comparison > 0:
            return f"{version} > allowed maxVersion {max_version}"
    return None


def _check_version_constraint(
    entry: ExtensionEntry,
    version: str | None,
    cause: str | None = None,
) -> tuple[bool | None, str | None]:
    """Compare *version* against the entry's minVersion / maxVersion.

    Returns ``(version_ok, reason)``:
    - ``(None, None)`` if the entry declares no constraint.
    - ``(True, None)`` if the observed version satisfies the constraint.
    - ``(False, reason)`` if the observed version violates the constraint
      (or if no version was extracted but a constraint is declared).

    When *version* is None and *cause* is supplied, the cause is woven
    into the reason so callers can see WHY extraction failed (timeout,
    non-zero exit, regex miss, OSError) instead of the prior generic
    "no version extracted" message that hid the upstream signal.
    """
    min_v = entry.get("minVersion")
    max_v = entry.get("maxVersion")
    if not min_v and not max_v:
        return None, None

    if version is None:
        bound = f">={min_v}" if min_v else f"<={max_v}"
        if cause:
            return False, f"{cause} (required {bound})"
        return False, f"no version extracted (required {bound})"

    failure_reason = _constraint_failure_reason(version, min_v, max_v)
    if failure_reason is not None:
        return False, failure_reason
    return True, None


_OUTPUT_SNIPPET_CAP = 80


def _first_line_snippet(output: str) -> str:
    """Return the first non-empty line of *output* clipped to the cap."""
    stripped = output.strip()
    if not stripped:
        return ""
    return stripped.splitlines()[0][:_OUTPUT_SNIPPET_CAP]


def _diagnose_version_failure(
    check: CheckConfig,
    exc: str | None,
    rc: int | None,
    output: str,
    version: str | None,
) -> str | None:
    """Return a one-line diagnostic when version extraction failed.

    Returns None when the version was extracted (no diagnostic needed)
    or when no versionPattern was declared (nothing to diagnose).
    Otherwise produces a string callers can pass through to operators -
    e.g. "TimeoutExpired(5s): ..." or "exit 127, output 'not found'"
    or "output 'hello' did not match (\\d+\\.\\d+\\.\\d+)".
    """
    if version is not None or "versionPattern" not in check:
        return None
    if exc:
        return exc
    if rc is not None and rc != 0:
        snippet = _first_line_snippet(output)
        if snippet:
            return f"exit {rc}, output {snippet!r}"
        return f"exit {rc}, no output"
    pattern = check.get("versionPattern", "")
    snippet = _first_line_snippet(output) or "<empty>"
    return f"output {snippet!r} did not match {pattern}"


def run_check(
    entry: ExtensionEntry,
    root: Path,
    *,
    log_hook: Callable[[CheckRecord], None] | None = None,
) -> HealthCheckResult:
    """Run health + version check. ``{python}`` -> hermetic interpreter. Max 5 s."""
    check = entry.get("check")
    if not check:
        # No check block - but minVersion/maxVersion can still be declared,
        # in which case we can't validate and must flag as such.
        v_ok, v_reason = _check_version_constraint(entry, None)
        healthy = v_ok is not False
        return HealthCheckResult(
            healthy=healthy,
            version=None,
            version_ok=v_ok,
            version_reason=v_reason,
        )

    binary = str(root / entry["binary"])
    venv_py = root / ".venv" / "bin" / "python"
    boot_py = root / ".boot-linux" / "python-env" / "bin" / "python"
    python_path = str(venv_py if venv_py.exists() else boot_py)
    cmd = [
        a.replace("{binary}", binary).replace("{python}", python_path)
        for a in check["command"]
    ]
    timeout = min(check.get("timeout", MAX_CHECK_TIMEOUT), MAX_CHECK_TIMEOUT)

    start = time.monotonic()
    rc: int | None = None
    stdout = stderr = ""
    exc: str | None = None
    output = ""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        rc, stdout, stderr = 0, r.stdout, r.stderr
        output = stdout + stderr
    except subprocess.CalledProcessError as cpe:
        rc = cpe.returncode
        stdout = cpe.stdout or ""
        stderr = cpe.stderr or ""
        output = stdout + stderr
    except subprocess.TimeoutExpired as e:
        exc = f"TimeoutExpired({timeout}s): {e}"
    except OSError as e:
        exc = f"OSError: {e}"

    elapsed = time.monotonic() - start
    health_ok = exc is None
    version: str | None = None
    if exc is None:
        if "healthExpect" in check:
            health_ok = check["healthExpect"] in output
        if "versionPattern" in check:
            m = re.search(check["versionPattern"], output)
            version = m.group(1) if m else None

    cause = _diagnose_version_failure(check, exc, rc, output, version)
    v_ok, v_reason = _check_version_constraint(entry, version, cause)

    if log_hook is not None:
        log_hook(
            CheckRecord(cmd, rc, stdout, stderr, elapsed, health_ok, version, exc),
        )
    return HealthCheckResult(
        healthy=health_ok,
        version=version,
        version_ok=v_ok,
        version_reason=v_reason,
    )
