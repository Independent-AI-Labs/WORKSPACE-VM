"""VM lifecycle — create, manage, and destroy agent containers."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import string
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7


class _VMExecError(RuntimeError):
    """Host PID or IP inspection failed for a VM."""


class _InvalidUIDError(RuntimeError):
    """id -u returned a non-numeric UID."""


_VMS_DIR = Path(".vms")
_TEMPLATES_DIR = Path("workspace/scripts/templates")
_CERTS_SCRIPT = Path("workspace/scripts/bootstrap/bootstrap_certs.sh")

_HEALTHCHECK_TIMEOUT = 120
_HEALTHCHECK_POLL = 2
_PODMAN_TIMEOUT = 600


def _podman(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["podman", *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=_PODMAN_TIMEOUT,
    )


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _render_template(name: str, context: Mapping[str, object]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        lstrip_blocks=True,
        trim_blocks=True,
    )
    return env.get_template(name).render(context)


def _config_sha256(config: VMConfig) -> str:
    raw = config.model_dump_json(exclude_defaults=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


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


def _generate_dockerignore(vm_dir: Path) -> None:
    (vm_dir / ".dockerignore").write_text(
        "password\npid\nvm.yaml\ncerts/\n.dockerignore\nDockerfile\n"
    )


def _pre_copy_files(config: VMConfig, uuid_str: str) -> None:
    if not config.files:
        return
    try:
        mountpoint = _podman(
            "volume", "inspect", "-f", "{{.Mountpoint}}", f"{uuid_str}-workspace"
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(
            "vm: WARNING: cannot inspect volume mountpoint, skipping pre-copy",
            file=sys.stderr,
        )
        return
    for entry in config.files:
        src = Path(os.path.expanduser(entry.src))
        dst = Path(mountpoint) / entry.dst.lstrip("/")
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _wait_healthy(uuid_str: str) -> None:
    deadline = time.monotonic() + _HEALTHCHECK_TIMEOUT
    while time.monotonic() < deadline:
        try:
            status = _podman(
                "inspect", "-f", "{{.State.Health.Status}}", uuid_str
            ).stdout.strip()
        except subprocess.CalledProcessError:
            time.sleep(_HEALTHCHECK_POLL)
            continue
        if status == "healthy":
            return
        time.sleep(_HEALTHCHECK_POLL)
    sys.stderr.write(
        f"vm: WARNING: healthcheck not healthy within "
        f"{_HEALTHCHECK_TIMEOUT}s for {uuid_str}\n"
    )


def _build_run_args(config: VMConfig, uuid_str: str) -> list[str]:
    run_args: list[str] = [
        "podman",
        "run",
        "-d",
        "--name",
        uuid_str,
        "--label",
        "ami.type=vm",
        "--label",
        f"ami.uuid={uuid_str}",
        "--label",
        f"ami.config={_config_sha256(config)}",
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
    run_args.append(f"ami-vm:{uuid_str}")
    return run_args


def _ensure_bridge_network(cfg: VMConfig) -> None:
    if cfg.network.mode != "bridge":
        return
    try:
        subprocess.run(
            ["podman", "network", "exists", cfg.network.network_name],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["podman", "network", "create", cfg.network.network_name],
            check=True,
        )


def _ensure_volume(vol_name: str) -> None:
    try:
        _podman("volume", "inspect", vol_name)
    except subprocess.CalledProcessError:
        _podman("volume", "create", vol_name)


def _build_context(
    cfg: VMConfig, password: str, vm_dir: Path, install_defaults: Path
) -> Mapping[str, object]:
    net_enabled = cfg.network.mode != "none"
    return {
        "security": cfg.security,
        "credentials": cfg.credentials,
        "ssh": cfg.ssh,
        "network": cfg.network,
        "traefik_enabled": net_enabled and cfg.web_ui,
        "network_enabled": net_enabled
        and cfg.network.policy
        in (
            "internet",
            "proxy",
        ),
        "openvpn_enabled": (
            cfg.network.mode == "openvpn" and cfg.network.vpn_type == "container"
        ),
        "password": password,
        "certs": str(vm_dir / "certs"),
        "vm_install_defaults": str(install_defaults),
    }


def _render_and_build(
    uuid_str: str, password: str, vm_dir: Path, context: Mapping[str, object]
) -> None:
    (vm_dir / "Dockerfile").write_text(_render_template("Dockerfile.vm.j2", context))
    _generate_dockerignore(vm_dir)
    _podman(
        "build",
        "-t",
        f"ami-vm:{uuid_str}",
        "--build-arg",
        f"AGENT_UID={_get_uid()}",
        "--build-arg",
        f"OPENCODE_SERVER_PASSWORD={password}",
        "-f",
        str(vm_dir / "Dockerfile"),
        ".",
    )


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


def create(config_path: str) -> None:
    cfg = VMConfig.model_validate(yaml.safe_load(Path(config_path).read_text()))
    uuid_str = uuid7()
    vm_dir = _VMS_DIR / uuid_str
    vm_dir.mkdir(parents=True, exist_ok=True)
    (vm_dir / "certs").mkdir(exist_ok=True)

    password = _generate_password()
    (vm_dir / "password").write_text(password)
    shutil.copy2(config_path, vm_dir / "vm.yaml")

    install_defaults = vm_dir / "vm-install-defaults.yaml"
    install_defaults.write_text(yaml.dump({"components": cfg.components}))

    context = _build_context(cfg, password, vm_dir, install_defaults)
    _render_and_build(uuid_str, password, vm_dir, context)

    _podman("volume", "create", f"{uuid_str}-workspace")
    _podman("volume", "create", f"{uuid_str}-transcripts")
    _podman("volume", "create", f"{uuid_str}-cache")
    _pre_copy_files(cfg, uuid_str)
    subprocess.run(
        ["bash", str(_CERTS_SCRIPT), uuid_str, str(vm_dir / "certs")],
        check=True,
    )
    _ensure_bridge_network(cfg)
    subprocess.run(_build_run_args(cfg, uuid_str), check=True)
    _post_run_inspect(uuid_str, vm_dir, cfg)
    _wait_healthy(uuid_str)

    print(f"VM {uuid_str} created")
    print(f"  UUID:     {uuid_str}")
    print(f"  Password: {password}")
    if cfg.network.mode == "bridge":
        print(f"  URL:      https://{uuid_str}.vm.local:443")
    print(f"  Cert:     {vm_dir / 'certs' / 'client.crt'}")


def rebuild(uuid_str: str) -> None:
    vm_yaml = _VMS_DIR / uuid_str / "vm.yaml"
    if not vm_yaml.exists():
        print(f"vm: no vm.yaml found for VM '{uuid_str}'", file=sys.stderr)
        sys.exit(1)
    cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
    vm_dir = _VMS_DIR / uuid_str
    password = (vm_dir / "password").read_text().strip()

    subprocess.run(
        ["podman", "rm", "-f", "--time", "1", uuid_str],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    _remove_hosts_entry(uuid_str)

    install_defaults = vm_dir / "vm-install-defaults.yaml"
    install_defaults.write_text(yaml.dump({"components": cfg.components}))
    context = _build_context(cfg, password, vm_dir, install_defaults)
    _render_and_build(uuid_str, password, vm_dir, context)

    for suffix in ("workspace", "transcripts", "cache"):
        _ensure_volume(f"{uuid_str}-{suffix}")

    subprocess.run(_build_run_args(cfg, uuid_str), check=True)
    _post_run_inspect(uuid_str, vm_dir, cfg)
    _wait_healthy(uuid_str)
    print(f"VM {uuid_str} rebuilt")


def sync(uuid_str: str) -> None:
    vm_yaml = _VMS_DIR / uuid_str / "vm.yaml"
    if not vm_yaml.exists():
        print(f"vm: no vm.yaml found for VM '{uuid_str}'", file=sys.stderr)
        sys.exit(1)
    cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
    if not cfg.sync:
        print(f"vm: no sync rules configured for VM '{uuid_str}'")
        return
    try:
        mountpoint = _podman(
            "volume", "inspect", "-f", "{{.Mountpoint}}", f"{uuid_str}-workspace"
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(f"vm: cannot find workspace volume for VM '{uuid_str}'", file=sys.stderr)
        sys.exit(1)
    synced = 0
    for entry in cfg.sync:
        src_dir = Path(os.path.expanduser(entry.dir))
        if not src_dir.is_dir():
            print(f"vm: sync: source directory '{src_dir}' not found, skipping")
            continue
        exclude_args: list[str] = []
        for pattern in entry.exclude:
            exclude_args.extend(["--exclude", pattern])
        rsync_cmd: list[str] = ["rsync", "-a", *exclude_args]
        if entry.strategy == "overwrite":
            rsync_cmd.append("--delete")
        subprocess.run([*rsync_cmd, f"{src_dir}/", str(mountpoint)], check=True)
        synced += 1
    label = "directory" if synced == 1 else "directories"
    print(f"vm: synced {synced} {label} to VM '{uuid_str}'")


def _remove_hosts_entry(uuid_str: str) -> None:
    hosts_file = Path("/etc/hosts")
    if not hosts_file.exists():
        return
    content = hosts_file.read_text()
    if f"{uuid_str}.vm.local" not in content:
        return
    new_lines = [
        line for line in content.splitlines() if f"{uuid_str}.vm.local" not in line
    ]
    try:
        hosts_file.write_text("\n".join(new_lines) + "\n")
    except PermissionError:
        sys.stderr.write(
            f"vm: WARNING: could not write /etc/hosts for {uuid_str} (try sudo)\n"
        )
