"""Apply VM config fields inside a running QEMU guest."""

from __future__ import annotations

import base64
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from workspace.cli.vpn_core import (
    find_workspace_root,
    resolve_vpn_auth,
    resolve_vpn_config,
)
from workspace.types.vm import VM_INSTALL_ROOT, VMConfig

_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SSH_OPTS = (
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "BatchMode=yes",
)


def _ssh(port: int, key: Path, script: str) -> None:
    subprocess.run(
        [
            "ssh",
            "-i",
            str(key),
            *_SSH_OPTS,
            "-p",
            str(port),
            "workspace@127.0.0.1",
            "bash",
            "-s",
        ],
        input=script,
        text=True,
        capture_output=True,
        check=True,
    )


def _rsync(port: int, key: Path, source: Path, destination: str) -> None:
    suffix = "/" if source.is_dir() else ""
    subprocess.run(
        [
            "rsync",
            "-a",
            "-e",
            (
                f"ssh -i {shlex.quote(str(key))} "
                f"-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                f"-o BatchMode=yes -p {port}"
            ),
            f"{source}{suffix}",
            f"workspace@127.0.0.1:{destination}",
        ],
        check=True,
    )


def _copy_file(port: int, key: Path, source: Path, destination: str) -> None:
    subprocess.run(
        [
            "scp",
            "-i",
            str(key),
            *_SSH_OPTS,
            "-P",
            str(port),
            str(source),
            f"workspace@127.0.0.1:{destination}",
        ],
        check=True,
    )


def _destination(value: str) -> str:
    if value.startswith("/") or ".." in Path(value).parts:
        msg = f"invalid guest destination: {value}"
        raise ValueError(msg)
    return f"/opt/workspace/{value}"


def _apply_env(port: int, key: Path, env: dict[str, str]) -> None:
    lines = []
    for name, value in env.items():
        if not _ENV_KEY.match(name):
            msg = f"invalid environment key: {name}"
            raise ValueError(msg)
        lines.append(f"{name}={shlex.quote(value)}")
    script = (
        "set -euo pipefail\n"
        "sudo install -d -m 0755 /etc/environment.d\n"
        "sudo tee /etc/environment.d/90-workspace.conf >/dev/null <<'EOF'\n"
        + "\n".join(lines)
        + "\nEOF\n"
    )
    _ssh(port, key, script)


def _apply_limits(port: int, key: Path, cfg: VMConfig) -> None:
    script = (
        "set -euo pipefail\n"
        "sudo install -d -m 0755 /etc/systemd/system.conf.d\n"
        "sudo tee /etc/systemd/system.conf.d/90-workspace.conf >/dev/null <<'EOF'\n"
        "[Manager]\n"
        f"DefaultTasksMax={cfg.resources.pids_limit}\n"
        "EOF\n"
        "sudo systemctl daemon-reexec\n"
    )
    _ssh(port, key, script)


def _proxy_host(proxy_url: str) -> str:
    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    if not parsed.hostname:
        msg = f"invalid proxy URL: {proxy_url}"
        raise ValueError(msg)
    return parsed.hostname


def _policy_script(cfg: VMConfig) -> str:
    rule = ""
    if cfg.network.policy == "internet":
        rule = (
            'nft add rule inet vm_policy output oifname "$iface" '
            "ip daddr { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, "
            "169.254.0.0/16 } drop\n"
        )
    elif cfg.network.policy == "proxy":
        host = _proxy_host(cfg.network.proxy_url)
        rule = (
            f'proxy_ip="$(getent ahostsv4 {shlex.quote(host)} '
            "| awk 'NR==1{print $1}')\"\n"
            'if [ -z "$proxy_ip" ]; then\n'
            '    echo "vm-network-policy: cannot resolve proxy host" >&2\n'
            "    exit 1\n"
            "fi\n"
            'nft add rule inet vm_policy output oifname "$iface" '
            'ip daddr != "$proxy_ip" drop\n'
        )
    return (
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        'iface=""\n'
        "for candidate in $(ip -o -4 addr show "
        "| awk '$4 !~ /^10\\.0\\.2\\./ && $4 !~ /^127\\./ "
        '{split($4,a,"/"); print $2}\'); do\n'
        '    iface="$candidate"\n'
        "    break\n"
        "done\n"
        'if [ -z "$iface" ]; then\n'
        '    echo "vm-network-policy: no bridge interface found" >&2\n'
        "    exit 1\n"
        "fi\n"
        "nft delete table inet vm_policy 2>/dev/null || true\n"
        "nft add table inet vm_policy\n"
        "nft add chain inet vm_policy output "
        "'{ type filter hook output priority 0; policy accept; }'\n"
        f"{rule}"
    )


def _apply_network_policy(port: int, key: Path, cfg: VMConfig) -> None:
    if cfg.network.mode != "bridge":
        return
    if cfg.network.policy == "unrestricted":
        return
    policy = _policy_script(cfg)
    proxy_env = ""
    if cfg.network.policy == "proxy":
        proxy_env = (
            "sudo tee /etc/environment.d/91-proxy.conf >/dev/null <<'EOF'\n"
            f"HTTP_PROXY={cfg.network.proxy_url}\n"
            f"HTTPS_PROXY={cfg.network.proxy_url}\n"
            "NO_PROXY=localhost,127.0.0.1\n"
            "EOF\n"
        )
    unit = (
        "[Unit]\n"
        "Description=QEMU guest network policy\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "RemainAfterExit=yes\n"
        "ExecStart=/usr/local/sbin/vm-network-policy\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    script = (
        "set -euo pipefail\n"
        "command -v nft >/dev/null\n"
        f"sudo tee /usr/local/sbin/vm-network-policy >/dev/null <<'POLICY'\n"
        f"{policy}"
        "POLICY\n"
        "sudo chmod 0755 /usr/local/sbin/vm-network-policy\n"
        f"{proxy_env}"
        "sudo tee /etc/systemd/system/vm-network-policy.service "
        ">/dev/null <<'EOF'\n"
        f"{unit}"
        "EOF\n"
        "sudo systemctl daemon-reload\n"
        "sudo systemctl enable --now vm-network-policy.service\n"
    )
    _ssh(port, key, script)


def _apply_mounts(port: int, key: Path, cfg: VMConfig) -> None:
    if not cfg.mounts:
        return
    lines = ["set -euo pipefail"]
    for index, entry in enumerate(cfg.mounts):
        target = shlex.quote(str(Path(entry).expanduser()))
        tag = shlex.quote(f"hostshare{index}")
        lines.append(f"sudo mkdir -p {target}")
        lines.append(f"sudo umount {target} 2>/dev/null || true")
        lines.append(
            f"sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro {tag} {target}"
        )
    _ssh(port, key, "\n".join(lines) + "\n")


def _apply_files(port: int, key: Path, cfg: VMConfig) -> None:
    for entry in cfg.files:
        source = Path(os.path.expanduser(entry.src))
        if not source.exists():
            msg = f"vm: file source not found: {source}"
            raise FileNotFoundError(msg)
        destination = _destination(entry.dst)
        parent = str(Path(destination).parent)
        _ssh(port, key, f"set -euo pipefail\nmkdir -p {shlex.quote(parent)}\n")
        _rsync(port, key, source, destination)


def _apply_ssh(port: int, key: Path, cfg: VMConfig) -> None:
    files: list[Path] = []
    if cfg.ssh.mode == "inherit":
        home = Path.home() / ".ssh"
        for name in ("id_ed25519", "id_rsa", "config", "known_hosts"):
            candidate = home / name
            if candidate.is_file():
                files.append(candidate)
    elif cfg.ssh.mode == "custom":
        files = [Path(os.path.expanduser(item)) for item in cfg.ssh.files]
    if not files:
        return
    _ssh(
        port,
        key,
        'set -euo pipefail\ninstall -d -m 0700 "$HOME/.ssh"\n',
    )
    for source in files:
        if not source.is_file():
            msg = f"vm: SSH file not found: {source}"
            raise FileNotFoundError(msg)
        _copy_file(port, key, source, f".ssh/{source.name}")
    _ssh(
        port,
        key,
        'set -euo pipefail\nchmod 0600 "$HOME/.ssh/"*\n',
    )


def _apply_provider(port: int, key: Path, cfg: VMConfig) -> None:
    if cfg.provider is None:
        return
    config = {
        "provider": {
            cfg.provider.name: {
                "npm": "@ai-sdk/openai-compatible",
                "options": cfg.provider.options,
            }
        },
        "server": {"port": 4096, "hostname": "127.0.0.1"},
    }
    encoded = base64.b64encode(json.dumps(config).encode()).decode()
    script = (
        "set -euo pipefail\n"
        'install -d -m 0700 "$HOME/.config/opencode"\n'
        f"printf '%s' {encoded} | base64 -d > "
        '"$HOME/.config/opencode/config.json"\n'
        'chmod 0600 "$HOME/.config/opencode/config.json"\n'
    )
    _ssh(port, key, script)


def _apply_credentials(port: int, key: Path, cfg: VMConfig) -> None:
    if cfg.credentials.mode == "api":
        msg = "vm: credentials.mode api is not supported for qemu"
        raise ValueError(msg)
    if cfg.credentials.mode != "clone":
        return
    source = Path.home() / ".config" / "opencode"
    if not source.is_dir():
        msg = f"vm: credentials source not found: {source}"
        raise FileNotFoundError(msg)
    _ssh(
        port,
        key,
        'set -euo pipefail\ninstall -d -m 0700 "$HOME/.config/opencode"\n',
    )
    _rsync(port, key, source, "~/.config/opencode/")


def _apply_web_ui(port: int, key: Path, cfg: VMConfig, vm_dir: Path) -> None:
    if not cfg.web_ui:
        return
    password = (vm_dir / "password").read_text().strip()
    service = (
        "[Unit]\n"
        "Description=opencode web UI\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        "User=workspace\n"
        "Group=workspace\n"
        f"WorkingDirectory={VM_INSTALL_ROOT}\n"
        "Environment=OPENCODE_ENABLE_EXA=1\n"
        f"Environment=OPENCODE_SERVER_PASSWORD={password}\n"
        f"ExecStart={VM_INSTALL_ROOT}/.boot-linux/bin/opencode web --port 4096\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    script = (
        "set -euo pipefail\n"
        f"test -x {VM_INSTALL_ROOT}/.boot-linux/bin/opencode\n"
        "sudo tee /etc/systemd/system/opencode.service >/dev/null <<'EOF'\n"
        f"{service}"
        "EOF\n"
        "sudo systemctl daemon-reload\n"
        "sudo systemctl enable --now opencode.service\n"
    )
    _ssh(port, key, script)


def _apply_openvpn(port: int, key: Path, cfg: VMConfig, vm_dir: Path) -> None:
    if cfg.network.mode != "openvpn" or cfg.network.vpn_type != "container":
        return
    workspace_root = find_workspace_root()
    config = resolve_vpn_config(workspace_root, cfg.network.vpn_config)
    auth = resolve_vpn_auth(workspace_root, cfg.network.vpn_auth)
    config_guest = "/tmp/workspace-openvpn-client.ovpn"
    _copy_file(port, key, config, config_guest)
    auth_guest = ""
    if auth is not None:
        auth_guest = "/tmp/workspace-openvpn-auth.txt"
        _copy_file(port, key, auth, auth_guest)
    auth_arg = ""
    if auth_guest:
        auth_arg = " --auth-user-pass /etc/openvpn/auth.txt"
    service = (
        "[Unit]\n"
        "Description=OpenVPN client\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        "User=root\n"
        f"ExecStart={VM_INSTALL_ROOT}/.boot-linux/bin/openvpn "
        f"--config /etc/openvpn/client.ovpn{auth_arg}\n"
        "Restart=on-failure\n"
        "RestartSec=10\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )
    install_auth = ""
    if auth_guest:
        install_auth = f"sudo install -m 0600 {auth_guest} /etc/openvpn/auth.txt\n"
    script = (
        "set -euo pipefail\n"
        f"test -x {VM_INSTALL_ROOT}/.boot-linux/bin/openvpn\n"
        "sudo install -d -m 0700 /etc/openvpn\n"
        f"sudo install -m 0600 {config_guest} /etc/openvpn/client.ovpn\n"
        f"{install_auth}"
        "sudo tee /etc/systemd/system/openvpn.service >/dev/null <<'EOF'\n"
        f"{service}"
        "EOF\n"
        "sudo systemctl daemon-reload\n"
        "sudo systemctl enable --now openvpn.service\n"
    )
    _ssh(port, key, script)


def apply_guest_config(
    cfg: VMConfig, vm_dir: Path, *, ssh_port: int | None = None
) -> None:
    if ssh_port is None:
        ssh_port = int((vm_dir / "ssh_port").read_text().strip())
    port = ssh_port
    key = vm_dir / "qemu_ssh_ed25519"
    _apply_mounts(port, key, cfg)
    _apply_limits(port, key, cfg)
    _apply_network_policy(port, key, cfg)
    if cfg.env:
        _apply_env(port, key, cfg.env)
    if cfg.files:
        _apply_files(port, key, cfg)
    if cfg.ssh.mode != "none":
        _apply_ssh(port, key, cfg)
    if cfg.provider is not None:
        _apply_provider(port, key, cfg)
    if cfg.credentials.mode != "none":
        _apply_credentials(port, key, cfg)
    _apply_openvpn(port, key, cfg, vm_dir)
    _apply_web_ui(port, key, cfg, vm_dir)


def apply_host_shares(
    vm_dir: Path, *, ssh_port: int | None = None, with_ci: bool = False
) -> None:
    if ssh_port is None:
        ssh_port = int((vm_dir / "ssh_port").read_text().strip())
    key = vm_dir / "qemu_ssh_ed25519"
    lines = [
        "set -euo pipefail",
        "sudo mkdir -p /mnt/workspace-ro /opt/workspace-ci",
        (
            "mountpoint -q /mnt/workspace-ro || "
            "sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro "
            "workspace /mnt/workspace-ro"
        ),
    ]
    if with_ci:
        lines.append(
            "mountpoint -q /opt/workspace-ci || "
            "sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro "
            "workspace-ci /opt/workspace-ci"
        )
    _ssh(ssh_port, key, "\n".join(lines) + "\n")


def apply_mounts(cfg: VMConfig, vm_dir: Path, *, ssh_port: int | None = None) -> None:
    if not cfg.mounts:
        return
    if ssh_port is None:
        ssh_port = int((vm_dir / "ssh_port").read_text().strip())
    _apply_mounts(ssh_port, vm_dir / "qemu_ssh_ed25519", cfg)
