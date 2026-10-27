"""QEMU isolation backend: subprocess-only, no libqemu linkage."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

import yaml

from workspace.cli.hypervisor.qemu_argv import QemuLaunchContext, build_qemu_argv
from workspace.cli.hypervisor.qemu_guest_config import (
    apply_guest_config,
    apply_host_shares,
    apply_mounts,
)
from workspace.cli.hypervisor.qemu_images import prepare_vm_storage
from workspace.cli.hypervisor.qemu_provision import provision_guest
from workspace.cli.hypervisor.qemu_qmp import QmpError, powerdown
from workspace.cli.hypervisor.qemu_resolve import (
    resolve_aarch64_firmware,
    resolve_accel,
    resolve_qemu_system,
)
from workspace.cli.hypervisor.qemu_state import (
    ensure_state,
    load_state,
    mark_error,
    mark_started,
    mark_stopped,
    process_identity,
    process_matches,
)
from workspace.cli.vm_core import _VMS_DIR, _generate_password
from workspace.cli.vpn_core import find_workspace_root
from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7

_HEALTH_TIMEOUT = 120
_PROVISION_SSH_TIMEOUT = 600
_HEALTH_POLL = 2
_STOP_TIMEOUT = 30
_TERM_TIMEOUT = 5
_CI_ROOT = Path("/opt/workspace-ci")
_MODE_ENV = "WORKSPACE_VM_MODE"
_QMP_SOCKET = "qmp.sock"


def _vm_mode(cfg: VMConfig) -> Literal["persistent", "ephemeral"]:
    mode = os.environ.get(_MODE_ENV, cfg.isolation.qemu.mode)
    if mode == "persistent":
        return "persistent"
    if mode == "ephemeral":
        return "ephemeral"
    msg = f"invalid {_MODE_ENV}: {mode!r}"
    raise ValueError(msg)


def _validate_network(cfg: VMConfig) -> None:
    if cfg.network.mode == "host":
        msg = "qemu does not support network.mode: host"
        raise ValueError(msg)
    if cfg.network.mode == "openvpn" and cfg.network.vpn_type == "netns":
        msg = "qemu does not support openvpn vpn_type: netns; use container"
        raise ValueError(msg)
    if cfg.network.mode != "bridge":
        return
    if not cfg.network.network_name or "," in cfg.network.network_name:
        msg = f"invalid qemu bridge name: {cfg.network.network_name!r}"
        raise ValueError(msg)
    if cfg.network.policy == "proxy" and not cfg.network.proxy_url:
        msg = "qemu bridge proxy policy requires network.proxy_url"
        raise ValueError(msg)
    if cfg.network.whitelist:
        msg = "qemu bridge does not support network.whitelist"
        raise ValueError(msg)


def _validate_mounts(cfg: VMConfig) -> None:
    for entry in cfg.mounts:
        path = Path(os.path.expanduser(entry))
        if not path.is_absolute():
            msg = f"qemu mount path must be absolute: {entry}"
            raise ValueError(msg)
        if "," in str(path):
            msg = f"qemu mount path must not contain a comma: {entry}"
            raise ValueError(msg)
        if not path.exists():
            msg = f"qemu mount source not found: {path}"
            raise FileNotFoundError(msg)


def _validate_config(cfg: VMConfig) -> None:
    _validate_network(cfg)
    _validate_mounts(cfg)
    if cfg.security.cap_add:
        msg = "qemu does not support security.cap_add"
        raise ValueError(msg)
    if cfg.credentials.mode == "api":
        msg = "qemu credentials.mode: api is not implemented"
        raise ValueError(msg)


def _pid_from_file(vm_dir: Path) -> int | None:
    path = vm_dir / "qemu.pid"
    if not path.is_file():
        return None
    value = path.read_text().strip()
    if not value.isdigit():
        msg = f"invalid QEMU PID file: {path}"
        raise ValueError(msg)
    return int(value)


def _resolve_ci_root() -> Path:
    if _CI_ROOT.is_dir():
        return _CI_ROOT
    msg = f"{_CI_ROOT} not found; run: sudo make -C projects/WORKSPACE-CI deploy-ci"
    raise FileNotFoundError(msg)


class QemuBackend:
    """Full Linux guest via qemu-system-*."""

    def backend_name(self) -> str:
        return "qemu"

    def create(self, config_path: str, cfg: VMConfig) -> None:
        _validate_config(cfg)
        uuid_str = uuid7()
        vm_dir = _VMS_DIR / uuid_str
        vm_dir.mkdir(parents=True, exist_ok=True)

        password = _generate_password()
        (vm_dir / "password").write_text(password)
        shutil.copy2(config_path, vm_dir / "vm.yaml")

        install_defaults = vm_dir / "vm-install-defaults.yaml"
        install_defaults.write_text(
            yaml.dump({"components": cfg.components, "extra_apt": cfg.extra_apt})
        )
        ensure_state(vm_dir, profile=cfg.isolation.qemu.provision, mode=_vm_mode(cfg))

        q = cfg.isolation.qemu
        workspace_root = find_workspace_root() if q.provision != "none" else None
        ci_root = _resolve_ci_root() if q.provision != "none" else None
        qemu_bin = resolve_qemu_system(q.guest_arch)
        accel = resolve_accel(q.accel, qemu_bin)
        firmware = resolve_aarch64_firmware() if q.guest_arch == "aarch64" else None
        if q.guest_arch == "aarch64" and firmware is None:
            print(
                "vm: WARNING: EDK2 firmware not found; guest may not boot "
                "(run make install-qemu)",
                file=sys.stderr,
            )

        ssh_port = int(prepare_vm_storage(cfg, vm_dir, mount_ci=ci_root is not None))
        launch = QemuLaunchContext(
            qemu_bin=qemu_bin,
            accel=accel,
            ssh_port=ssh_port,
            firmware=firmware,
            workspace_root=workspace_root,
            ci_root=ci_root,
            qmp_socket=vm_dir / _QMP_SOCKET,
            restrict_network=q.provision == "none",
        )
        argv = build_qemu_argv(cfg=cfg, vm_dir=vm_dir, launch=launch)
        try:
            subprocess.run(argv, check=True)
        except subprocess.CalledProcessError as exc:
            mark_error(vm_dir, f"qemu launch failed: {exc.returncode}")
            raise
        pid = _pid_from_file(vm_dir)
        pid_start = process_identity(pid) if pid is not None else None
        mark_started(vm_dir, ssh_port=ssh_port, pid_start=pid_start)
        ssh_key = vm_dir / "qemu_ssh_ed25519"
        ssh_timeout = (
            _HEALTH_TIMEOUT if q.provision == "none" else _PROVISION_SSH_TIMEOUT
        )
        _wait_ssh(int(ssh_port), ssh_key, timeout=ssh_timeout)

        if q.provision != "none":
            print("vm: provisioning guest (rsync + install-ci)...", file=sys.stderr)
            try:
                provision_guest(
                    cfg=cfg,
                    vm_dir=vm_dir,
                    ssh_port=int(ssh_port),
                    ssh_key=ssh_key,
                    install_defaults=install_defaults,
                )
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                mark_error(vm_dir, f"provisioning failed: {exc}")
                raise
        self._apply_and_restrict(cfg, vm_dir, uuid_str, int(ssh_port), q.provision)

        print(f"VM {uuid_str} created (qemu)")
        print(f"  UUID:     {uuid_str}")
        print(f"  Backend:  qemu ({accel})")
        ssh_key = vm_dir / "qemu_ssh_ed25519"
        print(f"  SSH:      ssh -i {ssh_key} -p {ssh_port} workspace@127.0.0.1")

    def _apply_and_restrict(
        self,
        cfg: VMConfig,
        vm_dir: Path,
        uuid: str,
        ssh_port: int,
        provision: str,
    ) -> None:
        try:
            apply_guest_config(cfg, vm_dir, ssh_port=ssh_port)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            mark_error(vm_dir, f"guest configuration failed: {exc}")
            raise
        if provision != "none":
            self.stop(uuid)
            self.start(uuid)

    def start(self, uuid: str, *, restrict_network: bool = True) -> None:
        vm_dir = _VMS_DIR / uuid
        vm_yaml = vm_dir / "vm.yaml"
        if not vm_yaml.is_file():
            msg = f"vm: no vm.yaml found for VM '{uuid}'"
            raise FileNotFoundError(msg)
        cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
        _validate_config(cfg)
        if self.status(uuid).get("state") == "running":
            return
        state = ensure_state(
            vm_dir, profile=cfg.isolation.qemu.provision, mode=_vm_mode(cfg)
        )
        pid = _pid_from_file(vm_dir)
        if pid is not None and _process_alive(pid):
            if state.pid_start is None or process_matches(pid, state.pid_start):
                return
            msg = f"vm: stale QEMU PID {pid} for VM '{uuid}'"
            raise RuntimeError(msg)
        (vm_dir / "qemu.pid").unlink(missing_ok=True)
        (vm_dir / _QMP_SOCKET).unlink(missing_ok=True)

        q = cfg.isolation.qemu
        qemu_bin = resolve_qemu_system(q.guest_arch)
        accel = resolve_accel(q.accel, qemu_bin)
        firmware = resolve_aarch64_firmware() if q.guest_arch == "aarch64" else None
        ssh_port = int((vm_dir / "ssh_port").read_text().strip())
        workspace_root = find_workspace_root() if q.provision != "none" else None
        ci_root = _resolve_ci_root() if q.provision != "none" else None
        launch = QemuLaunchContext(
            qemu_bin=qemu_bin,
            accel=accel,
            ssh_port=ssh_port,
            firmware=firmware,
            workspace_root=workspace_root,
            ci_root=ci_root,
            qmp_socket=vm_dir / _QMP_SOCKET,
            restrict_network=restrict_network and cfg.network.mode == "none",
        )
        argv = build_qemu_argv(cfg=cfg, vm_dir=vm_dir, launch=launch)
        try:
            subprocess.run(argv, check=True)
        except subprocess.CalledProcessError as exc:
            mark_error(vm_dir, f"qemu launch failed: {exc.returncode}")
            sys.stderr.write(f"qemu launch failed rc={exc.returncode}\n")
            raise
        new_pid = _pid_from_file(vm_dir)
        mark_started(
            vm_dir,
            ssh_port=ssh_port,
            pid_start=process_identity(new_pid) if new_pid is not None else None,
        )
        _wait_ssh(ssh_port, vm_dir / "qemu_ssh_ed25519")
        try:
            if q.provision != "none":
                apply_host_shares(vm_dir, ssh_port=ssh_port, with_ci=True)
            apply_mounts(cfg, vm_dir, ssh_port=ssh_port)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            mark_error(vm_dir, f"mount configuration failed: {exc}")
            raise

    def stop(self, uuid: str) -> None:
        vm_dir = _VMS_DIR / uuid
        if not vm_dir.is_dir():
            return
        pid = _pid_from_file(vm_dir)
        if pid is None:
            mark_stopped(vm_dir)
            return
        state = load_state(vm_dir)
        identity = state.pid_start if state is not None else None
        if not _process_alive(pid):
            (vm_dir / "qemu.pid").unlink(missing_ok=True)
            mark_stopped(vm_dir)
            return
        if identity is not None and not process_matches(pid, identity):
            msg = f"vm: QEMU PID {pid} does not match VM '{uuid}'"
            mark_error(vm_dir, msg)
            raise RuntimeError(msg)

        qmp = vm_dir / _QMP_SOCKET
        if qmp.exists():
            try:
                powerdown(qmp)
            except QmpError as exc:
                sys.stderr.write(f"vm: {exc}\n")
            if _wait_pid_exit(pid, _STOP_TIMEOUT):
                _finish_stop(vm_dir)
                return

        _signal(pid, "TERM")
        if _wait_pid_exit(pid, _TERM_TIMEOUT):
            _finish_stop(vm_dir)
            return
        _signal(pid, "KILL")
        if not _wait_pid_exit(pid, _TERM_TIMEOUT):
            msg = f"vm: QEMU PID {pid} did not exit"
            mark_error(vm_dir, msg)
            raise RuntimeError(msg)
        _finish_stop(vm_dir)

    def rebuild(self, uuid: str, *, fresh: bool = False) -> None:
        vm_dir = _VMS_DIR / uuid
        vm_yaml = vm_dir / "vm.yaml"
        if not vm_yaml.is_file():
            msg = f"vm: no vm.yaml found for VM '{uuid}'"
            raise FileNotFoundError(msg)
        cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
        self.stop(uuid)
        if fresh:
            backup = vm_dir / "backups"
            backup.mkdir(parents=True, exist_ok=True)
            disk = vm_dir / "disk.qcow2"
            if disk.is_file():
                stamp = int(time.time())
                disk.replace(backup / f"disk-{stamp}.qcow2")
            ci_root = (
                _resolve_ci_root() if cfg.isolation.qemu.provision != "none" else None
            )
            prepare_vm_storage(cfg, vm_dir, mount_ci=ci_root is not None)
        self.start(uuid, restrict_network=not fresh)
        ssh_port = int((vm_dir / "ssh_port").read_text().strip())
        try:
            if cfg.isolation.qemu.provision != "none":
                provision_guest(
                    cfg=cfg,
                    vm_dir=vm_dir,
                    ssh_port=ssh_port,
                    ssh_key=vm_dir / "qemu_ssh_ed25519",
                    install_defaults=vm_dir / "vm-install-defaults.yaml",
                )
            apply_guest_config(cfg, vm_dir, ssh_port=ssh_port)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            mark_error(vm_dir, f"rebuild failed: {exc}")
            raise
        if fresh and cfg.isolation.qemu.provision != "none":
            self.stop(uuid)
            self.start(uuid)

    def destroy(self, uuid: str, *, purge: bool = False) -> None:
        self.stop(uuid)
        vm_dir = _VMS_DIR / uuid
        if not vm_dir.is_dir():
            return
        if purge:
            shutil.rmtree(vm_dir)
            return
        archive = _VMS_DIR / "_archive"
        archive.mkdir(parents=True, exist_ok=True)
        destination = archive / uuid
        if destination.exists():
            msg = f"vm: archive already exists for VM '{uuid}': {destination}"
            raise FileExistsError(msg)
        shutil.move(str(vm_dir), str(destination))

    def exec(self, uuid: str, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        host, port = self.ssh_endpoint(uuid)
        key = _VMS_DIR / uuid / "qemu_ssh_ed25519"
        return subprocess.run(
            [
                "ssh",
                "-i",
                str(key),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-p",
                str(port),
                f"workspace@{host}",
                *cmd,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def ssh_endpoint(self, uuid: str) -> tuple[str, int]:
        port_file = _VMS_DIR / uuid / "ssh_port"
        return "127.0.0.1", int(port_file.read_text().strip())

    def status(self, uuid: str) -> dict[str, str]:
        vm_dir = _VMS_DIR / uuid
        pid_file = vm_dir / "qemu.pid"
        state = load_state(vm_dir)
        base: dict[str, str] = {"backend": "qemu"}
        if state is not None:
            base["mode"] = state.mode
            base["profile"] = state.profile
            if state.ssh_port is not None:
                base["ssh_port"] = str(state.ssh_port)
        disk = vm_dir / "disk.qcow2"
        if disk.is_file():
            base["disk_bytes"] = str(disk.stat().st_size)
        if state is not None and state.last_error:
            base["last_error"] = state.last_error
        if not pid_file.is_file():
            return {"state": "unknown", **base}
        pid_value = pid_file.read_text().strip()
        if not pid_value.isdigit():
            return {"state": "invalid", **base}
        pid = int(pid_value)
        if not _process_alive(pid):
            return {"state": "stopped", **base}
        if (
            state is not None
            and state.pid_start is not None
            and not process_matches(pid, state.pid_start)
        ):
            return {"state": "invalid", **base}
        return {"state": "running", "pid": pid_value, **base}


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal(pid: int, signal_name: str) -> None:
    try:
        subprocess.run(
            ["kill", f"-{signal_name}", str(pid)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            sys.stderr.write(exc.stderr)


def _wait_pid_exit(pid: int, timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(1)
    return not _process_alive(pid)


def _finish_stop(vm_dir: Path) -> None:
    (vm_dir / "qemu.pid").unlink(missing_ok=True)
    (vm_dir / _QMP_SOCKET).unlink(missing_ok=True)
    mark_stopped(vm_dir)


def _probe_ssh(port: int, identity: Path) -> bool:
    try:
        subprocess.run(
            [
                "ssh",
                "-i",
                str(identity),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "ConnectTimeout=3",
                "-p",
                str(port),
                "workspace@127.0.0.1",
                "echo",
                "ok",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def _wait_ssh(port: int, identity: Path, *, timeout: int = _HEALTH_TIMEOUT) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe_ssh(port, identity):
            return
        time.sleep(_HEALTH_POLL)
    print("vm: WARNING: SSH health check timed out", file=sys.stderr)
