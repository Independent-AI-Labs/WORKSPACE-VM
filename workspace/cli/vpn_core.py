"""Shared OpenVPN client utilities for host CLI and VM automation."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TextIO, TypedDict

VPN_CONFIG_REL = Path("workspace/config/vpn/client.ovpn")
VPN_AUTH_REL = Path("workspace/config/vpn/auth.txt")
OPENVPN_CONFIG_ENV = "OPENVPN_CONFIG_FILE"
OPENVPN_AUTH_ENV = "OPENVPN_AUTH_FILE"


class _VPNBinaryNotFoundError(FileNotFoundError):
    def __init__(self) -> None:
        super().__init__("openvpn not found; run bootstrap for the openvpn component")


class _VPNConfigNotFoundError(FileNotFoundError):
    def __init__(self, path: Path | str, *, env_var: str = "") -> None:
        detail = f"{env_var} not found: {path}" if env_var else str(path)
        super().__init__(detail)


class HealthCheckResult(TypedDict):
    """Health check result."""

    status: str
    connected: bool


def boot_name() -> str:
    """Return platform boot directory name."""
    return ".boot-macos" if platform.system() == "Darwin" else ".boot-linux"


def find_workspace_root(start: Path | None = None) -> Path:
    """Walk up from *start* to find the directory containing ``workspace/``."""
    current = (start or Path.cwd()).resolve()
    for _ in range(12):
        if (current / "workspace").is_dir():
            return current
        if current == current.parent:
            break
        current = current.parent
    return Path.cwd().resolve()


def find_openvpn_binary(workspace_root: Path) -> str:
    """Resolve boot-dir openvpn binary, then PATH."""
    boot_bin = workspace_root / boot_name() / "bin" / "openvpn"
    if boot_bin.is_file():
        return str(boot_bin)
    found = shutil.which("openvpn")
    if found:
        return found
    raise _VPNBinaryNotFoundError


def default_vpn_config_path(workspace_root: Path) -> Path:
    """Canonical gitignored client config path."""
    return workspace_root / VPN_CONFIG_REL


def default_vpn_auth_path(workspace_root: Path) -> Path:
    """Canonical gitignored auth file path."""
    return workspace_root / VPN_AUTH_REL


def resolve_vpn_config(workspace_root: Path, explicit: str = "") -> Path:
    """Resolve OpenVPN config: explicit path, env, then canonical default."""
    if explicit:
        path = Path(os.path.expanduser(explicit))
        if path.is_file():
            return path.resolve()
        raise _VPNConfigNotFoundError(path)
    env_val = os.environ.get(OPENVPN_CONFIG_ENV, "").strip()
    if env_val:
        path = Path(os.path.expanduser(env_val))
        if path.is_file():
            return path.resolve()
        raise _VPNConfigNotFoundError(path, env_var=OPENVPN_CONFIG_ENV)
    default = default_vpn_config_path(workspace_root)
    if default.is_file():
        return default.resolve()
    raise _VPNConfigNotFoundError(default)


def resolve_vpn_auth(workspace_root: Path, explicit: str = "") -> Path | None:
    """Resolve optional auth-user-pass file."""
    if explicit:
        path = Path(os.path.expanduser(explicit))
        return path.resolve() if path.is_file() else None
    env_val = os.environ.get(OPENVPN_AUTH_ENV, "").strip()
    if env_val:
        path = Path(os.path.expanduser(env_val))
        return path.resolve() if path.is_file() else None
    default = default_vpn_auth_path(workspace_root)
    return default.resolve() if default.is_file() else None


def validate_ovpn(path: Path) -> bool:
    """Return True when *path* looks like a usable OpenVPN client config."""
    if not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return any(marker in content for marker in ("remote ", "proto ", "dev "))


def _probe_command(cmd: list[str], *, text: bool = False) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, text=text, check=True)
    except subprocess.CalledProcessError:
        return False
    except OSError as exc:
        sys.stderr.write(f"vpn: probe failed ({' '.join(cmd)}): {exc}\n")
        return False
    return True


def tunnel_interface_up() -> bool:
    """Check for an active tun/utun tunnel interface."""
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["ifconfig", "-l"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return False
        except OSError as exc:
            sys.stderr.write(f"vpn: ifconfig failed: {exc}\n")
            return False
        return "utun" in (result.stdout or "")
    return _probe_command(["ip", "addr", "show", "tun0"])


def _pgrep_pattern(pattern: str) -> bool:
    return _probe_command(["pgrep", "-f", pattern])


def process_running(binary: str) -> bool:
    """Return True when *binary* appears in a running process command line."""
    return _pgrep_pattern(binary)


def workspace_openvpn_running(workspace_root: Path) -> bool:
    """Return True when the workspace client config or binary is running."""
    try:
        config = resolve_vpn_config(workspace_root)
        binary = find_openvpn_binary(workspace_root)
    except (_VPNConfigNotFoundError, _VPNBinaryNotFoundError):
        return False
    return _pgrep_pattern(str(config)) or _pgrep_pattern(binary)


def _recent_log_connected(lines: int = 20) -> bool:
    content = _read_vpn_log_lines(vpn_log_path(), lines)
    if not content:
        return False
    saw_init = False
    for line in reversed(content):
        if "SIGTERM" in line or "process exiting" in line:
            return False
        if "Initialization Sequence Completed" in line:
            saw_init = True
            break
    return saw_init


def vpn_connected(workspace_root: Path) -> bool:
    """Return True when the workspace openvpn client appears connected."""
    if not tunnel_interface_up():
        return False
    if workspace_openvpn_running(workspace_root):
        return True
    return _recent_log_connected()


def health_result(workspace_root: Path) -> HealthCheckResult:
    """Build health check payload."""
    connected = vpn_connected(workspace_root)
    return HealthCheckResult(
        status="connected" if connected else "disconnected",
        connected=connected,
    )


def openvpn_cmd(
    binary: str,
    config: Path,
    auth: Path | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    """Build an openvpn argv list."""
    cmd = [binary, "--config", str(config)]
    if auth is not None:
        cmd.extend(["--auth-user-pass", str(auth)])
    if extra:
        cmd.extend(extra)
    return cmd


def vpn_log_path() -> Path:
    """Return the host OpenVPN client log path for the current platform."""
    if sys.platform == "darwin":
        return Path("/var/log/workspace/openvpn.log")
    return Path.home() / ".local" / "state" / "workspace" / "openvpn.log"


def emit_vpn_log_tail(lines: int = 30, stream: TextIO | None = None) -> None:
    """Print the last *lines* from the OpenVPN client log."""
    out = stream or sys.stdout
    path = vpn_log_path()
    out.write(f"--- OpenVPN log: {path} (last {lines} lines) ---\n")
    if not path.is_file():
        out.write("(log file not created yet)\n")
        return
    content = _read_vpn_log_lines(path, lines)
    if content is None:
        out.write("(cannot read log; try: make vpn-logs)\n")
        return
    if not content:
        out.write("(empty)\n")
        return
    for line in content:
        out.write(f"{line}\n")


def _read_vpn_log_lines(path: Path, lines: int) -> list[str] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except PermissionError as exc:
        sys.stderr.write(f"vpn: cannot read log {path}: {exc}\n")
        return None
    except OSError as exc:
        sys.stderr.write(f"vpn: cannot read log {path}: {exc}\n")
        return None
    return text.splitlines()[-lines:]
