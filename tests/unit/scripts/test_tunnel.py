"""Tests for workspace/scripts/bin/tunnel.py."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

TUNNEL_PY = (
    Path(__file__).resolve().parents[3] / "workspace" / "scripts" / "bin" / "tunnel.py"
)

FAKE_EXIT_VERSION = 42
FAKE_EXIT_TUNNEL_CONFIG_VERSION = 7
FAKE_EXIT_CLI_CONFIG_VERSION = 9


def _run_tunnel(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env.pop("AMI_ROOT", None)
    run_env.pop("CLOUDFLARED_BIN", None)
    run_env.pop("TUNNEL_CONFIG", None)
    run_env.pop("CLOUDFLARED_CONFIG", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(TUNNEL_PY), *args],
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
    )


def test_no_args_prints_usage_without_crashing(tmp_path: Path) -> None:
    result = _run_tunnel()
    assert result.returncode == 0
    assert "CLOUDFLARED_BIN" in result.stderr
    assert "Examples:" in result.stderr


def test_cloudflared_bin_env_takes_precedence(tmp_path: Path) -> None:
    fake = tmp_path / "fake-cloudflared"
    fake.write_text("#!/bin/sh\nexit 42\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    result = _run_tunnel("version", env={"CLOUDFLARED_BIN": str(fake)})
    assert result.returncode == FAKE_EXIT_VERSION


def test_tunnel_config_injected_when_set(tmp_path: Path) -> None:
    fake = tmp_path / "fake-cloudflared"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--config" ] && [ "$3" = "version" ]; then exit 7; fi\n'
        "exit 1\n",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    config = tmp_path / "tunnel.yml"
    config.write_text("tunnel: test\n")

    result = _run_tunnel(
        "version",
        env={
            "CLOUDFLARED_BIN": str(fake),
            "TUNNEL_CONFIG": str(config),
        },
    )
    assert result.returncode == FAKE_EXIT_TUNNEL_CONFIG_VERSION


def test_cli_config_override_skips_env_injection(tmp_path: Path) -> None:
    fake = tmp_path / "fake-cloudflared"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--config" ] && [ "$2" = "/cli/config.yml" ]; then exit 9; fi\n'
        "exit 1\n",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env_config = tmp_path / "env.yml"
    env_config.write_text("tunnel: env\n")

    result = _run_tunnel(
        "--config",
        "/cli/config.yml",
        "version",
        env={
            "CLOUDFLARED_BIN": str(fake),
            "TUNNEL_CONFIG": str(env_config),
        },
    )
    assert result.returncode == FAKE_EXIT_CLI_CONFIG_VERSION


def test_missing_binary_returns_error() -> None:
    result = _run_tunnel(
        "tunnel", "list", env={"CLOUDFLARED_BIN": "/nonexistent/cloudflared"}
    )
    assert result.returncode == 1
    assert "cloudflared not found" in result.stderr


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(
    not (REPO_ROOT / ".boot-linux/bin/cloudflared").exists(),
    reason="cloudflared not bootstrapped in this environment",
)
def test_ami_root_alternate_root_finds_boot_binary() -> None:
    result = _run_tunnel(
        "--help",
        env={"AMI_ROOT": str(REPO_ROOT)},
    )
    assert result.returncode == 0
    assert "cloudflared" in result.stdout.lower()
