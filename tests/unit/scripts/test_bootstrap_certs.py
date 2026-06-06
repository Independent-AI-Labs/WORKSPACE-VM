"""Unit tests for Traefik and certs bootstrap scripts."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import yaml

BOOT_BIN = ".boot-linux/bin"


def test_bootstrap_traefik_script_exists() -> None:
    script = Path("workspace/scripts/bootstrap/bootstrap_traefik.sh")
    assert script.exists()
    assert script.is_file()
    assert script.stat().st_mode & stat.S_IXUSR


def test_bootstrap_traefik_has_component_entry() -> None:
    components_yaml = Path("workspace/config/bootstrap-components.yaml")
    data = yaml.safe_load(components_yaml.read_text())
    names = [c["name"] for c in data["components"]]
    assert "traefik" in names


def test_bootstrap_certs_script_exists() -> None:
    script = Path("workspace/scripts/bootstrap/bootstrap_certs.sh")
    assert script.exists()
    assert script.is_file()
    assert script.stat().st_mode & stat.S_IXUSR


def test_bootstrap_certs_generates_files(tmp_path: Path) -> None:
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    result = subprocess.run(
        [
            "bash",
            "workspace/scripts/bootstrap/bootstrap_certs.sh",
            "test-uuid",
            str(cert_dir),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,  # silent-ok: returncode asserted explicitly below
    )
    assert result.returncode == 0

    assert (cert_dir / "ca.crt").exists()
    assert (cert_dir / "ca.key").exists()
    assert (cert_dir / "server.crt").exists()
    assert (cert_dir / "server.key").exists()
    assert (cert_dir / "client.crt").exists()
    assert (cert_dir / "client.key").exists()

    ca_mode = (cert_dir / "ca.key").stat().st_mode
    assert ca_mode & stat.S_IRWXG == 0

    decoded = subprocess.run(
        [
            "openssl",
            "x509",
            "-in",
            str(cert_dir / "server.crt"),
            "-noout",
            "-subject",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "test-uuid.vm.local" in decoded.stdout

    decoded = subprocess.run(
        [
            "openssl",
            "x509",
            "-in",
            str(cert_dir / "client.crt"),
            "-noout",
            "-subject",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "CN" in decoded.stdout
    assert "ami-admin" in decoded.stdout


def test_bootstrap_certs_idempotent(tmp_path: Path) -> None:
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    args: list[str] = [
        "bash",
        "workspace/scripts/bootstrap/bootstrap_certs.sh",
        "idem-uuid",
        str(cert_dir),
    ]
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=30,
        check=False,  # silent-ok: returncode asserted below
    )
    assert result.returncode == 0
    first_mtime = (cert_dir / "server.crt").stat().st_mtime
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=30,
        check=False,  # silent-ok: returncode asserted below
    )
    assert result.returncode == 0
    second_mtime = (cert_dir / "server.crt").stat().st_mtime
    assert first_mtime == second_mtime
