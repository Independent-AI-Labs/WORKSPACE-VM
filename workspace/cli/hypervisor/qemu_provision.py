"""Post-boot guest provisioning: selective rsync + make install-ci."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from workspace.cli import process as proc
from workspace.types.vm import VM_INSTALL_ROOT, VMConfig

_GUEST_ROOT = VM_INSTALL_ROOT
_CI_ROOT = "/opt/workspace-ci"
_RO_MOUNT = "/mnt/workspace-ro"
_DEFAULT_TIMEOUT = 3600
_RSYNC_EXCLUDES = [
    ".vms/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".git/",
    "target/",
]

_SKELETON_PATHS = [
    "Makefile",
    "pyproject.toml",
    "moon.yml",
    "workspace/",
    "config/",
    "res/",
    "tests/",
]

_GUARD_PATHS = [
    "projects/WORKSPACE-GUARD/",
    "projects/WORKSPACE-CI/",
    "scripts/e2e/",
]

_FULL_CI_PARENT_PATHS = [
    "projects/WORKSPACE-CI/",
    "projects/WORKSPACE-DATAOPS/",
    "projects/WORKSPACE-GUARD/",
    "projects/WORKSPACE-BROWSER/",
]

_PROJECT_RSYNC_EXCLUDES = [item for item in _RSYNC_EXCLUDES if item != ".git/"]


class _SshSession:
    __slots__ = ("key", "port")

    def __init__(self, port: int, key: Path) -> None:
        self.port = port
        self.key = key


def provision_guest(
    *,
    cfg: VMConfig,
    vm_dir: Path,
    ssh_port: int,
    ssh_key: Path,
    install_defaults: Path,
) -> None:
    """Rsync workspace into guest disk and run install-ci when configured."""
    profile = cfg.isolation.qemu.provision
    if profile == "none":
        return

    timeout = int(os.environ.get("QEMU_PROVISION_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    log_path = vm_dir / "provision.log"
    log_lines: list[str] = []

    def _log(line: str) -> None:
        log_lines.append(line)
        log_path.write_text("\n".join(log_lines) + "\n")

    ssh = _SshSession(ssh_port, ssh_key)
    ro_timeout = int(os.environ.get("QEMU_RO_MOUNT_TIMEOUT", "600"))
    _wait_ro_mount(ssh, timeout=ro_timeout, log=_log)

    rsync_script = _build_rsync_script(profile)
    _ssh_run(ssh, rsync_script, timeout=timeout, log=_log)

    _scp_file(ssh, install_defaults, Path(f"{_GUEST_ROOT}/vm-install-defaults.yaml"))

    if os.environ.get("QEMU_RSYNC_BOOT", "0") == "1":
        boot_rsync = _build_boot_rsync_script()
        _ssh_run(ssh, boot_rsync, timeout=600, log=_log)

    install_script = _build_install_script(profile, cfg.extra_apt)
    _ssh_run(ssh, install_script, timeout=timeout, log=_log)
    if profile == "guard":
        _ssh_run(ssh, _build_guard_trust_script(), timeout=600, log=_log)
    _log("provision: complete")


def _wait_ro_mount(
    ssh: _SshSession,
    *,
    timeout: int,
    log: Callable[[str], None],
) -> None:
    deadline = time.monotonic() + timeout
    probe = f"test -f {_RO_MOUNT}/Makefile"
    while time.monotonic() < deadline:
        result = _ssh_run(ssh, probe, timeout=30, log=log, raise_on_error=False)
        if result.returncode == 0:
            log(f"provision: {_RO_MOUNT} ready")
            return
        time.sleep(5)
    msg = f"provision: timed out waiting for {_RO_MOUNT}"
    raise TimeoutError(msg)


def _paths_for_profile(profile: str) -> list[str]:
    paths = list(_SKELETON_PATHS)
    if profile == "guard":
        paths.extend(_GUARD_PATHS)
    elif profile == "full-ci":
        paths.extend(_FULL_CI_PARENT_PATHS)
    return paths


def _rsync_excludes(path: str) -> list[str]:
    if path.startswith("projects/"):
        return _PROJECT_RSYNC_EXCLUDES
    return _RSYNC_EXCLUDES


def _build_rsync_script(profile: str) -> str:
    lines = ["set -euo pipefail", f"sudo mkdir -p {_GUEST_ROOT}"]
    for path in _paths_for_profile(profile):
        src = f"{_RO_MOUNT}/{path}"
        dst = f"{_GUEST_ROOT}/{path}"
        dst_parent = Path(dst.rstrip("/")).parent
        exclude_args = " ".join(f"--exclude={item}" for item in _rsync_excludes(path))
        lines.append(f"sudo mkdir -p {dst_parent}")
        lines.append(f"sudo rsync -a {exclude_args} {src} {dst}")
    lines.append(f"sudo chown -R workspace:workspace {_GUEST_ROOT}")
    if profile == "guard":
        policy_dir = f"{_GUEST_ROOT}/projects/WORKSPACE-GUARD/config"
        lines.append(
            f"sudo find {policy_dir} -type f -name '*.yaml' "
            "-exec chown root:root {} +"
        )
    return "\n".join(lines) + "\n"


def _build_boot_rsync_script() -> str:
    return (
        "set -euo pipefail\n"
        f'if [ -d "{_RO_MOUNT}/.boot-linux" ]; then\n'
        f'  sudo mkdir -p "{_GUEST_ROOT}/.boot-linux"\n'
        f'  sudo rsync -a "{_RO_MOUNT}/.boot-linux/" "{_GUEST_ROOT}/.boot-linux/"\n'
        "fi\n"
    )


def _build_guard_trust_script() -> str:
    return (
        "set -euo pipefail\n"
        f"sudo chown -R root:root {_GUEST_ROOT}\n"
        f"sudo chmod -R go-w {_GUEST_ROOT}\n"
    )


def _build_install_script(profile: str, extra_apt: list[str]) -> str:
    lines = [
        "set -euo pipefail",
        f'export CI_WORKSPACE_ROOT="{_GUEST_ROOT}"',
    ]
    if profile == "full-ci":
        playwright = f"{_GUEST_ROOT}/.boot-linux/playwright-browsers"
        lines.append(f'export PLAYWRIGHT_BROWSERS_PATH="{playwright}"')
        lines.append(f"mkdir -p {_GUEST_ROOT}/.boot-linux/bin")
        lines.extend(
            [
                f"ln -sfn {_CI_ROOT}/.boot-linux/bin/{name} "
                f"{_GUEST_ROOT}/.boot-linux/bin/{name}"
                for name in ("uv", "node", "npm")
            ]
        )
    lines.extend([f'cd "{_GUEST_ROOT}"', "make init"])
    if profile == "guard":
        lines.append(
            "sudo make -C projects/WORKSPACE-GUARD build-shell-guard build-guard"
        )
        lines.append(
            "sudo env CARGO_HOME=/tmp/workspace-guard-cargo-0 "
            f"RUSTUP_HOME={_CI_ROOT}/.boot-linux/rust "
            f"PATH={_CI_ROOT}/.boot-linux/bin:$PATH "
            "cargo build --manifest-path projects/WORKSPACE-GUARD/Cargo.toml"
        )
    if profile != "guard":
        guest_defaults = f"{_GUEST_ROOT}/vm-install-defaults.yaml"
        lines.append(f"make install-ci INSTALL_DEFAULTS={guest_defaults}")
    return "\n".join(lines) + "\n"


def _scp_file(ssh: _SshSession, local: Path, remote: Path) -> None:
    proc.run(
        [
            "scp",
            "-i",
            str(ssh.key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-P",
            str(ssh.port),
            str(local),
            f"workspace@127.0.0.1:{remote}",
        ],
    )


def _ssh_run(
    ssh: _SshSession,
    remote_script: str,
    *,
    timeout: int,
    log: Callable[[str], None],
    raise_on_error: bool = True,
) -> subprocess.CompletedProcess[str]:
    log(f"provision: ssh ({len(remote_script)} byte script)")
    result = proc.run_result(
        [
            "ssh",
            "-i",
            str(ssh.key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-p",
            str(ssh.port),
            "workspace@127.0.0.1",
            "bash",
            "-s",
        ],
        input=remote_script,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.stdout:
        log(result.stdout.rstrip())
    if result.stderr:
        log(result.stderr.rstrip())
    if raise_on_error and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result
