"""Backend-aware VM lifecycle operations (start/stop/delete/list/shell/exec)."""

from __future__ import annotations

import os
import subprocess
import sys

import yaml

from workspace.cli.hypervisor.factory import get_backend
from workspace.cli.hypervisor.podman_backend import PodmanBackend
from workspace.cli.hypervisor.qemu_backend import QemuBackend
from workspace.cli.vm_core import _VMS_DIR
from workspace.types.vm import VMConfig


def load_vm_config(uuid: str) -> VMConfig:
    vm_yaml = _VMS_DIR / uuid / "vm.yaml"
    if not vm_yaml.is_file():
        print(f"vm: no vm.yaml found for VM '{uuid}'", file=sys.stderr)
        sys.exit(1)
    return VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))


def backend_for_uuid(uuid: str) -> PodmanBackend | QemuBackend:
    return get_backend(load_vm_config(uuid))


def _write_podman_pid(uuid: str) -> None:
    result = subprocess.run(
        ["podman", "inspect", "-f", "{{.State.Pid}}", uuid],
        capture_output=True,
        text=True,
        check=True,
    )
    (_VMS_DIR / uuid / "pid").write_text(result.stdout.strip())


def start(uuid: str) -> None:
    backend = backend_for_uuid(uuid)
    status = backend.status(uuid)
    if status.get("state") == "running":
        print(f"VM {uuid} already running")
        return
    backend.start(uuid)
    if backend.backend_name() == "podman":
        _write_podman_pid(uuid)
    print(f"VM {uuid} started")


def stop(uuid: str) -> None:
    backend = backend_for_uuid(uuid)
    backend.stop(uuid)
    (_VMS_DIR / uuid / "pid").unlink(missing_ok=True)
    print(f"VM {uuid} stopped")


def delete(uuid: str, *, purge: bool = False) -> None:
    backend = backend_for_uuid(uuid)
    backend.destroy(uuid, purge=purge)
    (_VMS_DIR / uuid / "pid").unlink(missing_ok=True)
    if purge:
        print(f"VM {uuid} deleted (volumes purged)")
    else:
        print(f"VM {uuid} deleted")


def shell(uuid: str) -> None:
    backend = backend_for_uuid(uuid)
    if backend.status(uuid).get("state") != "running":
        print(f"vm: shell: VM '{uuid}' is not running", file=sys.stderr)
        sys.exit(1)
    if backend.backend_name() == "qemu":
        host, port = backend.ssh_endpoint(uuid)
        key = _VMS_DIR / uuid / "qemu_ssh_ed25519"
        os.execvp(
            "ssh",
            [
                "ssh",
                "-t",
                "-i",
                str(key),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-p",
                str(port),
                f"workspace@{host}",
            ],
        )
    os.execvp(
        "podman",
        ["podman", "exec", "-it", "-u", "workspace", uuid, "/bin/bash"],
    )


def exec_cmd(uuid: str, cmd: list[str]) -> None:
    backend = backend_for_uuid(uuid)
    if backend.status(uuid).get("state") != "running":
        print(f"vm: exec: VM '{uuid}' is not running", file=sys.stderr)
        sys.exit(1)
    if backend.backend_name() == "qemu":
        result = backend.exec(uuid, cmd)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return
    os_exec = ["podman", "exec", uuid, *cmd]
    os.execvp("podman", os_exec)


def list_vms() -> None:
    rows: list[tuple[str, str, str]] = []
    if not _VMS_DIR.is_dir():
        print("No VMs found")
        return

    for vm_dir in sorted(_VMS_DIR.iterdir()):
        if not vm_dir.is_dir() or vm_dir.name.startswith("_"):
            continue
        vm_yaml = vm_dir / "vm.yaml"
        if not vm_yaml.is_file():
            continue
        uuid = vm_dir.name
        cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
        backend = get_backend(cfg)
        status = backend.status(uuid)
        rows.append((uuid, status.get("state", "unknown"), backend.backend_name()))

    if not rows:
        print("No VMs found")
        return

    print(f"{'NAME':<40} {'STATE':<10} {'BACKEND'}")
    for vm_name, state, backend_name in rows:
        print(f"{vm_name:<40} {state:<10} {backend_name}")


def show_status(uuid: str) -> None:
    backend = backend_for_uuid(uuid)
    info = backend.status(uuid)
    print(f"UUID:    {uuid}")
    print(f"Backend: {info.get('backend', backend.backend_name())}")
    print(f"State:   {info.get('state', 'unknown')}")
    if pid := info.get("pid"):
        print(f"PID:     {pid}")
    if backend.backend_name() == "podman":
        try:
            inspect = subprocess.run(
                ["podman", "inspect", uuid],
                capture_output=True,
                text=True,
                check=True,
            )
            sys.stdout.write(inspect.stdout)
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                sys.stderr.write(exc.stderr)
        try:
            stats = subprocess.run(
                ["podman", "stats", "--no-stream", uuid],
                capture_output=True,
                text=True,
                check=True,
            )
            sys.stdout.write(stats.stdout)
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                sys.stderr.write(exc.stderr)
    elif (log_file := _VMS_DIR / uuid / "qemu.log").is_file():
        print(f"Log:     {log_file}")


def show_logs(uuid: str, extra_args: list[str]) -> None:
    backend = backend_for_uuid(uuid)
    if backend.backend_name() == "qemu":
        log_file = _VMS_DIR / uuid / "qemu.log"
        if not log_file.is_file():
            print(f"vm: no qemu.log for VM '{uuid}'", file=sys.stderr)
            sys.exit(1)
        follow = "-f" in extra_args or "--follow" in extra_args
        tail_n = "50"
        for index, arg in enumerate(extra_args):
            if arg == "--tail" and index + 1 < len(extra_args):
                tail_n = extra_args[index + 1]
        if follow:
            subprocess.run(["tail", "-f", str(log_file)], check=True)
        else:
            subprocess.run(["tail", "-n", tail_n, str(log_file)], check=True)
        return
    subprocess.run(["podman", "logs", *extra_args, uuid], check=True)


def kill(uuid: str) -> None:
    backend = backend_for_uuid(uuid)
    if backend.backend_name() == "qemu":
        pid_file = _VMS_DIR / uuid / "qemu.pid"
        if not pid_file.is_file():
            print(f"vm: kill: no PID file for VM '{uuid}'", file=sys.stderr)
            sys.exit(1)
        pid = pid_file.read_text().strip()
        subprocess.run(["kill", "-SIGKILL", pid], check=True)
        print(f"VM {uuid} killed (SIGKILL sent to PID {pid})")
        return

    pid_file = _VMS_DIR / uuid / "pid"
    if not pid_file.is_file():
        print(f"vm: kill: no PID file for VM '{uuid}'", file=sys.stderr)
        sys.exit(1)
    pid = pid_file.read_text().strip()
    subprocess.run(["kill", "-SIGKILL", pid], check=True)
    print(f"VM {uuid} killed (SIGKILL sent to PID {pid})")
