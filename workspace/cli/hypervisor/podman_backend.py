"""Podman isolation backend: existing rootless container path."""

from __future__ import annotations

import shutil
import subprocess
import sys

import yaml

from workspace.cli.vm_build import (
    _build_context,
    _build_context_inputs,
    _build_run_args,
    _ensure_bridge_network,
    _generate_companion_files,
    _post_run_inspect,
    _pre_copy_files,
    _prepare_build_ssh_key,
    _render_and_build,
    _stage_vpn_assets,
)
from workspace.cli.vm_core import (
    _CERTS_SCRIPT,
    _VMS_DIR,
    _ensure_podman_machine,
    _generate_password,
    _podman,
    _remove_hosts_entry,
    _wait_healthy,
)
from workspace.cli.vpn_core import find_workspace_root
from workspace.cli.vpn_netns import ensure_vpn_netns
from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7


def _remove_volume(volume_name: str) -> None:
    try:
        subprocess.run(
            ["podman", "volume", "rm", "-f", volume_name],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            sys.stderr.write(exc.stderr)


def _purge_volumes(uuid: str) -> None:
    for suffix in ("workspace", "transcripts", "cache"):
        _remove_volume(f"{uuid}-{suffix}")


class PodmanBackend:
    """Rootless OCI containers via existing vm_build pipeline."""

    def backend_name(self) -> str:
        return "podman"

    def create(self, config_path: str, cfg: VMConfig) -> None:
        _ensure_podman_machine()
        uuid_str = uuid7()
        vm_dir = _VMS_DIR / uuid_str
        vm_dir.mkdir(parents=True, exist_ok=True)
        (vm_dir / "certs").mkdir(exist_ok=True)

        password = _generate_password()
        (vm_dir / "password").write_text(password)
        shutil.copy2(config_path, vm_dir / "vm.yaml")

        install_defaults = vm_dir / "vm-install-defaults.yaml"
        install_defaults.write_text(yaml.dump({"components": cfg.components}))

        ssh_key_relpath = _prepare_build_ssh_key(vm_dir)
        staged_vpn = _stage_vpn_assets(vm_dir, cfg)
        context = _build_context(
            cfg,
            password,
            vm_dir,
            _build_context_inputs(install_defaults, ssh_key_relpath, staged_vpn),
        )
        _generate_companion_files(vm_dir, cfg, context)
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
        if (
            cfg.network.mode == "openvpn"
            and cfg.network.vpn_type == "netns"
            and sys.platform != "darwin"
        ):
            ensure_vpn_netns(cfg, find_workspace_root())
        subprocess.run(_build_run_args(cfg, uuid_str), check=True)
        _post_run_inspect(uuid_str, vm_dir, cfg)
        _wait_healthy(uuid_str)

        print(f"VM {uuid_str} created")
        print(f"  UUID:     {uuid_str}")
        print("  Backend:  podman")
        print(f"  Password: {password}")
        if cfg.network.mode == "bridge":
            print(f"  URL:      https://{uuid_str}.vm.local:443")
        print(f"  Cert:     {vm_dir / 'certs' / 'client.crt'}")

    def start(self, uuid: str) -> None:
        _podman("start", uuid)

    def stop(self, uuid: str) -> None:
        _podman("stop", uuid)

    def destroy(self, uuid: str, *, purge: bool = False) -> None:
        status = self.status(uuid)
        if status.get("state") == "running":
            _podman("rm", "-f", uuid)
        else:
            _podman("rm", uuid)
        try:
            subprocess.run(
                ["podman", "rmi", "-f", f"workspace-vm:{uuid}"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                sys.stderr.write(exc.stderr)
        _remove_hosts_entry(uuid)
        if purge:
            _purge_volumes(uuid)

    def exec(self, uuid: str, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["podman", "exec", uuid, *cmd],
            capture_output=True,
            text=True,
            check=True,
        )

    def ssh_endpoint(self, uuid: str) -> tuple[str, int]:
        msg = f"ssh_endpoint not applicable to podman backend (uuid={uuid})"
        raise NotImplementedError(msg)

    def status(self, uuid: str) -> dict[str, str]:
        running = _podman("inspect", "-f", "{{.State.Running}}", uuid).stdout.strip()
        state = "running" if running == "true" else "stopped"
        return {"state": state, "backend": "podman"}
