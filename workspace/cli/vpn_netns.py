"""Linux host network-namespace OpenVPN setup for VM netns attach mode."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from workspace.cli.vpn_core import (
    find_openvpn_binary,
    resolve_vpn_auth,
    validate_ovpn,
)
from workspace.types.vm import VMConfig


class _VPNNetnsSetupError(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class _NetnsScriptMissing(_VPNNetnsSetupError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"netns setup script not found: {path}")


class _NetnsConfigMissing(_VPNNetnsSetupError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"VPN config not found: {path}")


class _NetnsConfigInvalid(_VPNNetnsSetupError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"invalid OpenVPN config: {path}")


class _NetnsAuthMissing(_VPNNetnsSetupError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"VPN auth file not found: {path}")


class _NetnsCommandFailed(_VPNNetnsSetupError):
    def __init__(self) -> None:
        super().__init__(
            "VPN netns setup failed; ensure sudo is available for ip netns"
        )


def _resolve_vpn_host_path(path_str: str, workspace_root: Path) -> Path:
    expanded = Path(path_str).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (workspace_root / expanded).resolve()


def ensure_vpn_netns(cfg: VMConfig, workspace_root: Path) -> None:
    """Create netns and start OpenVPN before podman run in netns attach mode."""
    if sys.platform == "darwin":
        return

    script = workspace_root / "workspace/scripts/bin/setup_vpn_netns.sh"
    if not script.is_file():
        raise _NetnsScriptMissing(script)

    binary = find_openvpn_binary(workspace_root)
    config = _resolve_vpn_host_path(cfg.network.vpn_config, workspace_root)
    if not config.is_file():
        raise _NetnsConfigMissing(config)
    if not validate_ovpn(config):
        raise _NetnsConfigInvalid(config)

    auth_path: Path | None = None
    if cfg.network.vpn_auth:
        auth_path = _resolve_vpn_host_path(cfg.network.vpn_auth, workspace_root)
        if not auth_path.is_file():
            raise _NetnsAuthMissing(auth_path)
    else:
        auth_path = resolve_vpn_auth(workspace_root)

    cmd = [
        "bash",
        str(script),
        "--netns",
        cfg.network.vpn_netns,
        "--config",
        str(config),
        "--binary",
        binary,
    ]
    if auth_path is not None:
        cmd.extend(["--auth", str(auth_path)])

    try:
        subprocess.run(cmd, check=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise _NetnsCommandFailed from exc
