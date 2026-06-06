"""VM lifecycle CLI — create, manage, and destroy agent containers."""

from __future__ import annotations

import hashlib
import secrets
import string
import subprocess
from pathlib import Path
from typing import TypedDict

import yaml
from jinja2 import Environment, FileSystemLoader

from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7

_VMS_DIR = Path(".vms")
_TEMPLATES_DIR = Path("workspace/scripts/templates")
_CERTS_SCRIPT = Path("workspace/scripts/bootstrap/bootstrap_certs.sh")


def _podman(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["podman", *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class VMTemplateContext(TypedDict, total=False):
    security: object
    credentials: object
    ssh: object
    network: object
    traefik_enabled: bool
    network_enabled: bool
    openvpn_enabled: bool
    password: str
    certs: str


def _render_template(name: str, context: VMTemplateContext) -> str:
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


def create(config_path: str) -> None:
    cfg = VMConfig.model_validate(yaml.safe_load(Path(config_path).read_text()))

    uuid_str = uuid7()
    vm_dir = _VMS_DIR / uuid_str
    vm_dir.mkdir(parents=True, exist_ok=True)
    (vm_dir / "certs").mkdir(exist_ok=True)

    password = _generate_password()
    (vm_dir / "password").write_text(password)

    Path(config_path).replace(vm_dir / "vm.yaml")

    network_enabled = cfg.network.mode != "none"
    traefik_enabled = network_enabled and cfg.web_ui
    openvpn_enabled = (
        cfg.network.mode == "openvpn" and cfg.network.vpn_type == "container"
    )

    context: VMTemplateContext = {
        "security": cfg.security,
        "credentials": cfg.credentials,
        "ssh": cfg.ssh,
        "network": cfg.network,
        "traefik_enabled": traefik_enabled,
        "network_enabled": network_enabled
        and cfg.network.policy
        in (
            "internet",
            "proxy",
        ),
        "openvpn_enabled": openvpn_enabled,
        "password": password,
        "certs": str(vm_dir / "certs"),
    }

    (vm_dir / "Dockerfile").write_text(_render_template("Dockerfile.vm.j2", context))

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

    _podman("volume", "create", f"{uuid_str}-workspace")
    _podman("volume", "create", f"{uuid_str}-transcripts")
    _podman("volume", "create", f"{uuid_str}-cache")

    subprocess.run(
        ["bash", str(_CERTS_SCRIPT), uuid_str, str(vm_dir / "certs")],
        check=True,
    )

    if cfg.network.mode == "bridge":
        subprocess.run(
            ["podman", "network", "exists", cfg.network.network_name],
            capture_output=True,
            check=False,
        )

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
        f"ami.config={_config_sha256(cfg)}",
        "-v",
        f"{uuid_str}-workspace:/workspace",
        "-v",
        f"{uuid_str}-transcripts:/transcripts",
        "-v",
        f"{uuid_str}-cache:/cache",
        "--userns=keep-id",
        "--memory",
        cfg.resources.memory,
        "--cpus",
        str(cfg.resources.cpus),
        "--pids-limit",
        str(cfg.resources.pids_limit),
        *(_derive_network_flags(cfg)),
        *(_derive_cap_flags(cfg)),
    ]
    if cfg.security.no_new_privileges:
        run_args.extend(["--security-opt", "no-new-privileges"])
    if cfg.security.read_only_rootfs:
        run_args.extend(
            [
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid",
                "--tmpfs",
                "/run:rw,noexec,nosuid",
            ]
        )
    run_args.append(f"ami-vm:{uuid_str}")
    subprocess.run(run_args, check=True)

    try:
        inspect_result = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Pid}}", uuid_str],
            capture_output=True,
            text=True,
            check=True,
        )
        (vm_dir / "pid").write_text(inspect_result.stdout.strip())

        if cfg.network.mode == "bridge":
            ip_result = subprocess.run(
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
            container_ip = ip_result.stdout.strip()
            if container_ip:
                hosts_entry = f"{container_ip} {uuid_str}.vm.local\n"
                with open("/etc/hosts", "a") as f:
                    f.write(hosts_entry)
    except subprocess.CalledProcessError:
        print(f"Warning: could not determine host PID or IP for {uuid_str}")

    print(f"VM {uuid_str} created")
    print(f"  UUID:     {uuid_str}")
    print(f"  Password: {password}")


def _get_uid() -> str:
    return (
        subprocess.run(
            ["id", "-u"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or "1000"
    )
