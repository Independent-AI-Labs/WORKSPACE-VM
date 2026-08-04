from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from workspace.cli.vpn_core import (
    _VPNConfigNotFoundError,
    emit_vpn_log_tail,
    find_openvpn_binary,
    find_workspace_root,
    health_result,
    openvpn_cmd,
    resolve_vpn_auth,
    resolve_vpn_config,
    validate_ovpn,
    vpn_connected,
    vpn_log_path,
    workspace_openvpn_running,
)

_SERVICE_SCRIPT_REL = Path("workspace/scripts/bootstrap/bootstrap_openvpn_service.sh")
_SYSTEMD_UNIT = "workspace-openvpn.service"
_LAUNCHD_LABEL = "workspace.openvpn.client"
_LAUNCHD_DOMAIN = "system" if platform.system() == "Darwin" else ""
_KICKSTART_TIMEOUT = 10
_START_WAIT = 30
_LOG_TAIL_LINES = 30
_TIMEOUT_EXIT = 124


def _workspace_root() -> Path:
    ami_root = os.environ.get("AMI_ROOT", "").strip()
    if ami_root:
        return Path(ami_root).resolve()
    return find_workspace_root()


def _launchd_target() -> str:
    return f"{_LAUNCHD_DOMAIN}/{_LAUNCHD_LABEL}"


def _launchctl_cmd(*args: str) -> list[str]:
    cmd = ["launchctl", *args]
    if platform.system() == "Darwin":
        return ["sudo", *cmd]
    return cmd


def _wait_for_vpn_up(root: Path, deadline: float) -> bool:
    remaining = max(1, int(deadline - time.monotonic()))
    print(f"Waiting for VPN (up to {remaining}s)...", file=sys.stderr, flush=True)
    while time.monotonic() < deadline:
        if vpn_connected(root):
            print("VPN is connected.", file=sys.stderr, flush=True)
            return True
        if workspace_openvpn_running(root):
            print("OpenVPN process is running (tunnel not up yet)...", file=sys.stderr)
        time.sleep(1)
    return False


def _command_returncode(cmd: list[str], *, timeout: float | None = None) -> int:
    try:
        subprocess.run(cmd, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return _TIMEOUT_EXIT
    except subprocess.CalledProcessError as exc:
        return exc.returncode if exc.returncode is not None else 1
    else:
        return 0


def _service_script(root: Path) -> Path:
    return root / _SERVICE_SCRIPT_REL


def _install_service(root: Path) -> int:
    binary = find_openvpn_binary(root)
    script = _service_script(root)
    return _command_returncode(["bash", str(script), str(root), binary])


def _darwin_kickstart() -> int:
    print(f"Starting LaunchDaemon: {_launchd_target()}", file=sys.stderr, flush=True)
    rc = _command_returncode(
        _launchctl_cmd("kickstart", "-k", _launchd_target()),
        timeout=_KICKSTART_TIMEOUT,
    )
    if rc == _TIMEOUT_EXIT:
        print(
            "launchctl kickstart timed out (daemon may still be starting).",
            file=sys.stderr,
        )
        return 0
    if rc != 0:
        print(
            f"launchctl kickstart exit {rc}",
            file=sys.stderr,
        )
    return rc


def _start_daemon(root: Path, _config: Path, _auth: Path | None) -> int:
    if platform.system() == "Darwin":
        plist = Path("/Library/LaunchDaemons") / f"{_LAUNCHD_LABEL}.plist"
        if not plist.is_file():
            print(
                f"LaunchDaemon not installed: {plist}; run: make vpn-install",
                file=sys.stderr,
            )
            return 1
        if vpn_connected(root):
            print("VPN is already connected.", file=sys.stderr, flush=True)
            return 0
        _darwin_kickstart()
    else:
        print(
            f"Starting systemd user unit: {_SYSTEMD_UNIT}",
            file=sys.stderr,
            flush=True,
        )
        rc = _command_returncode(["systemctl", "--user", "start", _SYSTEMD_UNIT])
        if rc != 0:
            print(
                f"systemctl start failed (exit {rc})",
                file=sys.stderr,
            )
            return rc
    if _wait_for_vpn_up(root, time.monotonic() + _START_WAIT):
        return 0
    print("VPN did not connect in time.", file=sys.stderr)
    return 1


def _stop_service() -> int:
    if platform.system() == "Darwin":
        print(
            f"Stopping LaunchDaemon: {_launchd_target()}", file=sys.stderr, flush=True
        )
        return _command_returncode(_launchctl_cmd("bootout", _launchd_target()))
    print(f"Stopping systemd user unit: {_SYSTEMD_UNIT}", file=sys.stderr, flush=True)
    return _command_returncode(["systemctl", "--user", "stop", _SYSTEMD_UNIT])


def _start_foreground(binary: str, config: Path, auth: Path | None) -> int:
    cmd = openvpn_cmd(binary, config, auth)
    print(f"Starting OpenVPN client: {' '.join(cmd)}", flush=True)
    return _command_returncode(cmd)


def _report_daemon_start(rc: int) -> int:
    emit_vpn_log_tail(_LOG_TAIL_LINES)
    if rc != 0:
        print(
            f"vpn: start failed (exit {rc}); log: {vpn_log_path()}",
            file=sys.stderr,
        )
    else:
        print("vpn: start complete", file=sys.stderr, flush=True)
    return rc


def _action_health(root: Path) -> int:
    print(json.dumps(health_result(root)))
    return 0


def _action_status(root: Path, ovpn_file: str) -> int:
    try:
        binary = find_openvpn_binary(root)
        config = resolve_vpn_config(root, ovpn_file)
    except (FileNotFoundError, _VPNConfigNotFoundError) as exc:
        print(f"status: {exc}", file=sys.stderr)
        return 1
    connected = health_result(root)["connected"]
    print(f"binary:  {binary}")
    print(f"config:  {config}")
    print(f"log:     {vpn_log_path()}")
    print(f"connected: {'yes' if connected else 'no'}")
    return 0


def _action_stop() -> int:
    rc = _stop_service()
    emit_vpn_log_tail(_LOG_TAIL_LINES, stream=sys.stderr)
    return rc


def _action_start(root: Path, ovpn_file: str, auth_file: str, daemon: bool) -> int:
    try:
        config = resolve_vpn_config(root, ovpn_file)
    except _VPNConfigNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    if not validate_ovpn(config):
        print(f"invalid OpenVPN config: {config}", file=sys.stderr)
        return 1
    auth = resolve_vpn_auth(root, auth_file)
    if daemon:
        return _report_daemon_start(_start_daemon(root, config, auth))
    binary = find_openvpn_binary(root)
    return _start_foreground(binary, config, auth)


def main() -> int:
    """OpenVPN client CLI for host automation."""
    parser = argparse.ArgumentParser(description="Workspace OpenVPN client")
    parser.add_argument("--ovpn-file")
    parser.add_argument("--auth-file")
    parser.add_argument(
        "--action",
        default="start",
        choices=["start", "stop", "health", "status", "install-service"],
    )
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()

    root = _workspace_root()
    if args.action == "install-service":
        return _install_service(root)
    if args.action == "health":
        return _action_health(root)
    if args.action == "status":
        return _action_status(root, args.ovpn_file or "")
    if args.action == "stop":
        return _action_stop()
    if args.action == "start":
        return _action_start(
            root,
            args.ovpn_file or "",
            args.auth_file or "",
            args.daemon,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
