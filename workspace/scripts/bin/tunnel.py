#!/usr/bin/env python3
"""AMI Cloudflare Tunnel Wrapper.

Smart wrapper for cloudflared with AMI-aware tunnel configuration defaults.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _ami_root() -> str:
    """Get AMI_ROOT."""
    root = os.environ.get("AMI_ROOT")
    if not root:
        print("Error: AMI_ROOT not set", file=sys.stderr)
        sys.exit(1)
    return root


def _find_cloudflared() -> str | None:
    """Find the bootstrapped cloudflared binary."""
    root = Path(_ami_root())
    boot_name = ".boot-macos" if platform.system() == "Darwin" else ".boot-linux"
    boot = root / boot_name / "bin" / "cloudflared"
    if boot.exists():
        return str(boot)
    return shutil.which("cloudflared")


def _find_config() -> str | None:
    """Find cloudflared config from AMI config dir."""
    root = Path(_ami_root())
    for name in ["cloudflared.yml", "cloudflared.yaml", "tunnel.yml"]:
        config = root / "ami" / "config" / name
        if config.exists():
            return str(config)
    return None


def main() -> int:
    """Main entry point - pass through to cloudflared with AMI defaults."""
    args = list(sys.argv[1:])

    if any(a in ("-h", "--help") for a in args):
        binary = _find_cloudflared()
        if binary:
            try:
                return subprocess.run([binary, "--help"], check=True).returncode
            except subprocess.CalledProcessError as exc:
                return exc.returncode
        print(
            "AMI Cloudflare Tunnel wrapper\n"
            "Error: cloudflared not found. Run bootstrap to install it.",
            file=sys.stderr,
        )
        return 0

    binary = _find_cloudflared()
    if not binary:
        print(
            "Error: cloudflared not found. Run bootstrap to install it.",
            file=sys.stderr,
        )
        return 1

    # Inject config if user hasn't specified one and we have an AMI config
    has_config = any(a in ("--config", "-c") for a in args)
    if not has_config:
        config = _find_config()
        if config:
            args = ["--config", config, *args]

    cmd = [binary, *args]
    return subprocess.run(cmd, check=True).returncode


if __name__ == "__main__":
    sys.exit(main())
