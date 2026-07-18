"""VM lifecycle - create and rebuild agent environments."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from workspace.cli.hypervisor.factory import get_backend
from workspace.cli.vm_build import (
    _build_context,
    _build_context_inputs,
    _build_run_args,
    _ensure_volume,
    _generate_companion_files,
    _post_run_inspect,
    _prepare_build_ssh_key,
    _render_and_build,
    _stage_vpn_assets,
)
from workspace.cli.vm_core import (
    _VMS_DIR,
    _ensure_podman_machine,
    _remove_hosts_entry,
    _wait_healthy,
)
from workspace.cli.vpn_core import find_workspace_root
from workspace.cli.vpn_netns import ensure_vpn_netns
from workspace.types.vm import VMConfig


def create(config_path: str) -> None:
    cfg = VMConfig.model_validate(yaml.safe_load(Path(config_path).read_text()))
    get_backend(cfg).create(config_path, cfg)


def rebuild(uuid_str: str) -> None:
    vm_yaml = _VMS_DIR / uuid_str / "vm.yaml"
    if not vm_yaml.exists():
        print(f"vm: no vm.yaml found for VM '{uuid_str}'", file=sys.stderr)
        sys.exit(1)
    cfg = VMConfig.model_validate(yaml.safe_load(vm_yaml.read_text()))
    if cfg.isolation.backend == "qemu":
        print("vm: rebuild not supported for qemu backend yet", file=sys.stderr)
        sys.exit(1)

    _ensure_podman_machine()
    vm_dir = _VMS_DIR / uuid_str
    password = (vm_dir / "password").read_text().strip()

    try:
        subprocess.run(
            ["podman", "rm", "-f", "--time", "1", uuid_str],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"vm: podman rm failed rc={exc.returncode}: {exc.stderr}\n")
        raise
    _remove_hosts_entry(uuid_str)

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

    for suffix in ("workspace", "transcripts", "cache"):
        _ensure_volume(f"{uuid_str}-{suffix}")

    if (
        cfg.network.mode == "openvpn"
        and cfg.network.vpn_type == "netns"
        and sys.platform != "darwin"
    ):
        ensure_vpn_netns(cfg, find_workspace_root())
    subprocess.run(_build_run_args(cfg, uuid_str), check=True)
    _post_run_inspect(uuid_str, vm_dir, cfg)
    _wait_healthy(uuid_str)
    print(f"VM {uuid_str} rebuilt")
