"""VM build pipeline - Dockerfile rendering, podman build, run, and inspection."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from workspace.cli.vm_core import (
    _config_sha256,
    _generate_dockerignore,
    _podman,
    _render_template,
)
from workspace.types.vm import (
    VM_CONTAINER_HOME,
    VM_CONTAINER_USER,
    VM_IMAGE_PREFIX,
    VM_INSTALL_ROOT,
    VM_LABEL_PREFIX,
    VMConfig,
)


class _VMExecError(RuntimeError):
    """Host PID or IP inspection failed for a VM."""


class _InvalidUIDError(RuntimeError):
    """id -u returned a non-numeric UID."""


def _get_uid() -> str:
    result = subprocess.run(
        ["id", "-u"],
        capture_output=True,
        text=True,
        check=True,
    )
    uid = result.stdout.strip()
    if not uid or not uid.isdigit():
        raise _InvalidUIDError
    return uid


def _prepare_build_ssh_key(vm_dir: Path) -> str:
    """Stage host SSH key for container build; return repo-relative COPY path."""
    dest = vm_dir / "temp_ssh_key"
    src = Path.home() / ".ssh" / "id_rsa"
    if src.is_file():
        shutil.copy2(src, dest)
        dest.chmod(0o600)
    else:
        dest.touch()
    return os.path.relpath(dest.resolve(), Path.cwd().resolve())


def _derive_network_flags(config: VMConfig) -> list[str]:
    flags: list[str] = []
    mode = config.network.mode
    if mode == "none":
        flags.extend(["--network", "none"])
    elif mode == "bridge":
        flags.extend(["--network", config.network.network_name])
    elif mode == "host":
        flags.extend(["--network", "host"])
    elif mode == "openvpn":
        if config.network.vpn_type == "netns":
            flags.extend(["--network", f"ns:/run/netns/{config.network.vpn_netns}"])
        else:
            flags.extend(["--network", config.network.network_name])
            flags.extend(["--device", "/dev/net/tun"])
    return flags


def _derive_cap_flags(config: VMConfig) -> list[str]:
    flags: list[str] = []
    for cap in config.security.cap_drop:
        flags.extend(["--cap-drop", cap])
    if not config.security.cap_add:
        if config.network.mode == "bridge" and config.network.policy in (
            "internet",
            "proxy",
        ):
            flags.extend(["--cap-add", "NET_ADMIN"])
        if config.network.mode == "openvpn" and config.network.vpn_type == "container":
            flags.extend(["--cap-add", "NET_ADMIN"])
    else:
        for cap in config.security.cap_add:
            flags.extend(["--cap-add", cap])
    return flags


def _pre_copy_files(config: VMConfig, uuid_str: str) -> None:
    if not config.files:
        return
    try:
        result = subprocess.run(
            [
                "podman",
                "volume",
                "inspect",
                "-f",
                "{{.Mountpoint}}",
                f"{uuid_str}-workspace",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError:
        print(
            "vm: WARNING: cannot inspect volume mountpoint, skipping pre-copy",
            file=sys.stderr,
        )
        return
    mountpoint = result.stdout.strip()
    for entry in config.files:
        src = Path(os.path.expanduser(entry.src))
        dst = Path(mountpoint) / entry.dst.lstrip("/")
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _build_run_args(config: VMConfig, uuid_str: str) -> list[str]:
    run_args: list[str] = [
        "podman",
        "run",
        "-d",
        "--systemd=always",
        "--name",
        uuid_str,
        "--label",
        f"{VM_LABEL_PREFIX}.type=vm",
        "--label",
        f"{VM_LABEL_PREFIX}.uuid={uuid_str}",
        "--label",
        f"{VM_LABEL_PREFIX}.config={_config_sha256(config)}",
        "-v",
        f"{uuid_str}-workspace:/workspace",
        "-v",
        f"{uuid_str}-transcripts:/transcripts",
        "-v",
        f"{uuid_str}-cache:/cache",
        "--userns=keep-id",
        "--memory",
        config.resources.memory,
        "--cpus",
        str(config.resources.cpus),
        "--pids-limit",
        str(config.resources.pids_limit),
        "--health-on-failure=stop",
        *(_derive_network_flags(config)),
        *(_derive_cap_flags(config)),
    ]
    if config.security.no_new_privileges:
        run_args.extend(["--security-opt", "no-new-privileges"])
    if config.security.read_only_rootfs:
        run_args.extend(
            [
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid",
                "--tmpfs",
                "/run:rw,noexec,nosuid",
            ]
        )
    for env_key, env_val in config.env.items():
        run_args.extend(["-e", f"{env_key}={env_val}"])
    for mount_entry in config.mounts:
        run_args.extend(["--mount", f"type=bind,src={mount_entry},ro"])
    run_args.append(f"{VM_IMAGE_PREFIX}:{uuid_str}")
    return run_args


def _ensure_bridge_network(cfg: VMConfig) -> None:
    if cfg.network.mode != "bridge":
        return
    try:
        subprocess.run(
            ["podman", "network", "exists", cfg.network.network_name],
            capture_output=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["podman", "network", "create", cfg.network.network_name],
            check=True,
            timeout=30,
        )


def _ensure_volume(vol_name: str) -> None:
    try:
        subprocess.run(
            ["podman", "volume", "inspect", vol_name],
            capture_output=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["podman", "volume", "create", vol_name],
            check=True,
            timeout=30,
        )


def _build_context(
    cfg: VMConfig,
    password: str,
    vm_dir: Path,
    install_defaults: Path,
    vm_temp_ssh_key_relpath: str,
) -> Mapping[str, object]:
    net_enabled = cfg.network.mode != "none"
    return {
        "security": cfg.security,
        "credentials": cfg.credentials,
        "ssh": cfg.ssh,
        "network": cfg.network,
        "traefik_enabled": net_enabled and cfg.web_ui,
        "network_enabled": net_enabled and cfg.network.policy in ("internet", "proxy"),
        "openvpn_enabled": (
            cfg.network.mode == "openvpn" and cfg.network.vpn_type == "container"
        ),
        "password": password,
        "certs": str(vm_dir / "certs"),
        "vm_install_defaults": str(install_defaults),
        "vm_temp_ssh_key_relpath": vm_temp_ssh_key_relpath,
        "vm_opencode_json": str(vm_dir / "vm-opencode.json"),
        "vm_opencode_service": str(vm_dir / "vm-opencode.service"),
        "vm_traefik_service": str(vm_dir / "vm-traefik.service"),
        "vm_traefik_static": str(vm_dir / "vm-traefik-static.yml"),
        "vm_traefik_dynamic": str(vm_dir / "vm-traefik-dynamic.yml"),
        "vm_workspace_network_service": str(vm_dir / "vm-workspace-network.service"),
        "vm_openvpn_service": str(vm_dir / "vm-openvpn.service"),
        "container_user": VM_CONTAINER_USER,
        "container_home": VM_CONTAINER_HOME,
        "container_install_root": VM_INSTALL_ROOT,
        "policy": cfg.network.policy,
        "proxy_url": cfg.network.proxy_url,
    }


def _render_and_build(
    uuid_str: str,
    password: str,
    vm_dir: Path,
    context: Mapping[str, object],
) -> None:
    (vm_dir / "Dockerfile").write_text(_render_template("Dockerfile.vm.j2", context))
    _generate_dockerignore(vm_dir)
    build_args = ["build", "--format", "docker"]
    if sys.platform != "darwin":
        build_args.extend(["--ssh", "default"])
    build_args.extend(
        [
            "-t",
            f"{VM_IMAGE_PREFIX}:{uuid_str}",
            "--build-arg",
            f"AGENT_UID={_get_uid()}",
            "--build-arg",
            f"OPENCODE_SERVER_PASSWORD={password}",
            "-f",
            str(vm_dir / "Dockerfile"),
            ".",
        ]
    )
    ssh_key = vm_dir / "temp_ssh_key"
    try:
        _podman(*build_args)
    finally:
        if ssh_key.exists():
            ssh_key.unlink()


def _post_run_inspect(uuid_str: str, vm_dir: Path, cfg: VMConfig) -> None:
    try:
        pid = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Pid}}", uuid_str],
            capture_output=True,
            text=True,
            check=True,
        )
        (vm_dir / "pid").write_text(pid.stdout.strip())
        if cfg.network.mode == "bridge":
            ip = subprocess.run(
                [
                    "podman",
                    "inspect",
                    "-f",
                    f"{{{{.NetworkSettings.Networks.{cfg.network.network_name}.IPAddress}}}}",
                    uuid_str,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            container_ip = ip.stdout.strip()
            if container_ip:
                with open("/etc/hosts", "a") as f:
                    f.write(f"{container_ip} {uuid_str}.vm.local\n")
    except subprocess.CalledProcessError as exc:
        raise _VMExecError from exc


def _generate_companion_files(
    vm_dir: Path, cfg: VMConfig, context: Mapping[str, object]
) -> None:
    if cfg.provider:
        opencode_cfg = {
            "provider": {
                cfg.provider.name: {
                    "npm": "@ai-sdk/openai-compatible",
                    "options": cfg.provider.options,
                }
            },
            "server": {"port": 4096, "hostname": "127.0.0.1"},
        }
    else:
        opencode_cfg = {"server": {"port": 4096, "hostname": "127.0.0.1"}}
    (vm_dir / "vm-opencode.json").write_text(json.dumps(opencode_cfg))
    svc = _render_template("systemd-opencode.service.j2", context)
    (vm_dir / "vm-opencode.service").write_text(svc)
    if context.get("traefik_enabled"):
        (vm_dir / "vm-traefik.service").write_text(
            _render_template("systemd-traefik.service.j2", context)
        )
        (vm_dir / "vm-traefik-static.yml").write_text(
            _render_template("traefik-static.yml.j2", context)
        )
        (vm_dir / "vm-traefik-dynamic.yml").write_text(
            _render_template("traefik-dynamic.yml.j2", context)
        )
    if context.get("network_enabled"):
        (vm_dir / "vm-workspace-network.service").write_text(
            _render_template("systemd-workspace-network.service.j2", context)
        )
    if context.get("openvpn_enabled"):
        (vm_dir / "vm-openvpn.service").write_text(
            _render_template("systemd-openvpn.service.j2", context)
        )
