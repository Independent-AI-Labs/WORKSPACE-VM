"""VM lifecycle - create and rebuild agent containers."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from workspace.cli.vm_build import (
    _build_context,
    _build_run_args,
    _ensure_bridge_network,
    _ensure_volume,
    _generate_companion_files,
    _post_run_inspect,
    _pre_copy_files,
    _render_and_build,
)
from workspace.cli.vm_core import (
    _CERTS_SCRIPT,
    _VMS_DIR,
    _generate_password,
    _podman,
    _remove_hosts_entry,
    _wait_healthy,
)
from workspace.types.vm import VMConfig
from workspace.utils.uuid_utils import uuid7


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
    _generate_companion_files(vm_dir, cfg, context)
    _render_and_build(uuid_str, password, vm_dir, context)

    for suffix in ("workspace", "transcripts", "cache"):
        _ensure_volume(f"{uuid_str}-{suffix}")

    subprocess.run(_build_run_args(cfg, uuid_str), check=True)
    _post_run_inspect(uuid_str, vm_dir, cfg)
    _wait_healthy(uuid_str)
    print(f"VM {uuid_str} rebuilt")
