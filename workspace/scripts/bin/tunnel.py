#!/usr/bin/env python3
"""AMI Cloudflare Tunnel Wrapper.

Passthrough to cloudflared. Binary and config paths are env-driven to avoid
hard dependencies on AMI_ROOT (prevents circular bootstrap deps).

Environment:
  CLOUDFLARED_BIN    - explicit path to cloudflared binary
  TUNNEL_CONFIG      - config file passed as --config when not overridden on CLI
  CLOUDFLARED_CONFIG - alias for TUNNEL_CONFIG
  AMI_ROOT           - optional alternate root for boot-binary discovery only
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_cloudflared() -> str | None:
    """Resolve cloudflared binary: CLOUDFLARED_BIN, then AMI boot bin, then PATH."""
    explicit = os.environ.get("CLOUDFLARED_BIN", "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        return None

    ami_root = os.environ.get("AMI_ROOT", "").strip()
    if ami_root:
        boot_name = ".boot-macos" if platform.system() == "Darwin" else ".boot-linux"
        boot_bin = Path(ami_root) / boot_name / "bin" / "cloudflared"
        if boot_bin.is_file() and os.access(boot_bin, os.X_OK):
            return str(boot_bin)

    found = shutil.which("cloudflared")
    return found or None


def _resolve_config() -> str | None:
    """Resolve tunnel config from TUNNEL_CONFIG or CLOUDFLARED_CONFIG."""
    for key in ("TUNNEL_CONFIG", "CLOUDFLARED_CONFIG"):
        value = os.environ.get(key, "").strip()
        if not value:
            continue
        path = Path(value)
        if path.is_file():
            return str(path)
    return None


def _wrapper_usage() -> str:
    return """AMI Cloudflare Tunnel wrapper (cloudflared passthrough)

Environment:
  CLOUDFLARED_BIN     Path to cloudflared (optional; else AMI_ROOT boot bin or PATH)
  TUNNEL_CONFIG       Config file auto-passed as --config when set
  CLOUDFLARED_CONFIG  Alias for TUNNEL_CONFIG
  AMI_ROOT            Optional; used only to locate .boot-linux/bin/cloudflared

Examples:
  tunnel tunnel login
  tunnel tunnel create <name>
  tunnel tunnel route dns <name> <hostname>
  tunnel tunnel --config /path/to/config.yml run

Run 'tunnel --help' for cloudflared command reference.
"""


def _cloudflared_not_found_message() -> None:
    print(
        "Error: cloudflared not found. Set CLOUDFLARED_BIN or run bootstrap.",
        file=sys.stderr,
    )


def _run_cloudflared(cmd: list[str]) -> int:
    try:
        return subprocess.call(cmd)
    except OSError as exc:
        print(f"Error: failed to run {cmd[0]}: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    """Pass through to cloudflared with optional config injection."""
    args = list(sys.argv[1:])

    if not args:
        print(_wrapper_usage(), file=sys.stderr)
        return 0

    binary = _resolve_cloudflared()
    if any(a in ("-h", "--help") for a in args):
        if not binary:
            print(_wrapper_usage(), file=sys.stderr)
            _cloudflared_not_found_message()
            return 1
        return _run_cloudflared([binary, "--help"])

    if not binary:
        _cloudflared_not_found_message()
        return 1

    has_config = any(a in ("--config", "-c") for a in args)
    if not has_config:
        config = _resolve_config()
        if config:
            args = ["--config", config, *args]

    return _run_cloudflared([binary, *args])


if __name__ == "__main__":
    sys.exit(main())
