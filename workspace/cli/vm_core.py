"""VM core utilities - shared constants and helper functions."""

from __future__ import annotations

import hashlib
import os
import secrets
import string
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from workspace.cli.vpn_core import boot_name
from workspace.types.vm import VMConfig

_VMS_DIR = Path(os.environ.get("WS_VM_DIR", ".vms"))
_TEMPLATES_DIR = Path("workspace/scripts/templates")
_CERTS_SCRIPT = Path("workspace/scripts/bootstrap/bootstrap_certs.sh")

_HEALTHCHECK_TIMEOUT = 120
_HEALTHCHECK_POLL = 2
_PODMAN_TIMEOUT = 600

# Runtime binaries come from the deployed trust boundary provisioned by
# deploy-ci (see vpn_core pathfinding seam + AGENTS.md): single explicit
# source or fail. Checkout boot copies are forbidden (removed 2026-09-12).
_DEPLOYED_BOOT_BIN = Path("/opt/workspace-ci") / boot_name() / "bin"


class PodmanNotDeployedError(RuntimeError):
    """Raised when the deployed podman runtime is missing."""


def _podman_binary() -> Path:
    """Resolve the deployed podman wrapper; fail explicitly if absent."""
    binary = _DEPLOYED_BOOT_BIN / "podman"
    if not binary.is_file():
        msg = f"deployed podman missing at {binary} - run: sudo make init"
        raise PodmanNotDeployedError(msg)
    return binary


def _podman(*args: str, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(_podman_binary()), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=_PODMAN_TIMEOUT,
            env={**os.environ},
        )
    except subprocess.CalledProcessError as exc:
        # quiet=True is for handled-outcome probes (e.g. status() treating
        # a missing container as absent) where the caller translates the
        # failure; printing per-miss stderr would spam listings.
        if not quiet:
            if exc.stderr:
                sys.stderr.write(exc.stderr)
            if exc.stdout:
                sys.stdout.write(exc.stdout)
        raise


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _render_template(name: str, context: Mapping[str, object]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        lstrip_blocks=True,
        trim_blocks=True,
    )
    return env.get_template(name).render(context)


def _config_sha256(config: str | VMConfig) -> str:
    if isinstance(config, str):
        raw = config
    else:
        raw = config.model_dump_json(exclude_defaults=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _generate_dockerignore(vm_dir: Path) -> None:
    (vm_dir / ".dockerignore").write_text(
        "password\npid\nvm.yaml\ncerts/\n.dockerignore\nDockerfile\n"
    )


def _wait_healthy(uuid_str: str) -> None:
    deadline = time.monotonic() + _HEALTHCHECK_TIMEOUT
    while time.monotonic() < deadline:
        try:
            status = _podman(
                "inspect", "-f", "{{.State.Health.Status}}", uuid_str
            ).stdout.strip()
        except subprocess.CalledProcessError:
            time.sleep(_HEALTHCHECK_POLL)
            continue
        if status == "healthy":
            return
        time.sleep(_HEALTHCHECK_POLL)
    sys.stderr.write(
        f"vm: WARNING: healthcheck not healthy within "
        f"{_HEALTHCHECK_TIMEOUT}s for {uuid_str}\n"
    )


class _PodmanMachineError(RuntimeError):
    """macOS podman machine is missing or not running."""


def _ensure_podman_machine() -> None:
    """On Darwin, require the podman-machine-default machine to exist and run."""
    if sys.platform != "darwin":
        return
    machine = "podman-machine-default"
    try:
        subprocess.run(
            ["podman", "machine", "inspect", machine],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        msg = (
            f"vm: podman machine '{machine}' is not configured. "
            "Run: podman machine init && podman machine start"
        )
        raise _PodmanMachineError(msg) from exc
    state = subprocess.run(
        ["podman", "machine", "inspect", "--format", "{{.State}}", machine],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    if state.stdout.strip() != "running":
        msg = (
            f"vm: podman machine '{machine}' is not running "
            f"(state={state.stdout.strip()}). Run: podman machine start"
        )
        raise _PodmanMachineError(msg)


def _remove_hosts_entry(uuid_str: str) -> None:
    hosts_file = Path("/etc/hosts")
    if not hosts_file.exists():
        return
    content = hosts_file.read_text()
    if f"{uuid_str}.vm.local" not in content:
        return
    new_lines = [
        line for line in content.splitlines() if f"{uuid_str}.vm.local" not in line
    ]
    try:
        hosts_file.write_text("\n".join(new_lines) + "\n")
    except PermissionError:
        sys.stderr.write(
            f"vm: WARNING: could not write /etc/hosts for {uuid_str} (try sudo)\n"
        )
