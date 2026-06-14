#!/usr/bin/env bash
# Renders the systemd service files, traefik configs, and Dockerfile into
# the build context directory. All input paths are passed as arguments.
# Output is written to "${VMS_DIR}/${CONTAINER_NAME}/".

set -euo pipefail

PROJECT_ROOT="$1"
VM_DIR="$2"
PASSWORD_FILE="$3"
TEMPLATES_DIR="$4"
PYTHON_BIN="$5"

vm_dir="$VM_DIR"
vm_name="$(basename "$vm_dir")"

"$PYTHON_BIN" << PYTHON
import json
import sys
from pathlib import Path

sys.path.insert(0, '${PROJECT_ROOT}')

from jinja2 import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader('${TEMPLATES_DIR}'),
    lstrip_blocks=True,
    trim_blocks=True,
)

password = open('${PASSWORD_FILE}').read().strip()

opencode_template = env.get_template("systemd-opencode.service.j2")
with open('${vm_dir}/vm-opencode.service', 'w') as f:
    f.write(opencode_template.render(
        home="/home/workspace",
        workspace_root="/opt/workspace",
        network_enabled=True,
        traefik_enabled=True,
        password=password,
    ))

network_template = env.get_template("systemd-workspace-network.service.j2")
with open('${vm_dir}/vm-workspace-network.service', 'w') as f:
    f.write(network_template.render(
        workspace_root="/opt/workspace",
        network_mode="bridge",
        vpn_type="container",
        policy="internet",
        proxy_url="",
    ))

traefik_service_template = env.get_template("systemd-traefik.service.j2")
with open('${vm_dir}/vm-traefik.service', 'w') as f:
    f.write(traefik_service_template.render(
        network_enabled=True,
    ))

traefik_static_template = env.get_template("traefik-static.yml.j2")
with open('${vm_dir}/traefik-static.yml', 'w') as f:
    f.write(traefik_static_template.render())

traefik_dynamic_template = env.get_template("traefik-dynamic.yml.j2")
with open('${vm_dir}/traefik-dynamic.yml', 'w') as f:
    f.write(traefik_dynamic_template.render())

opencode_config = {
    "server": {"host": "127.0.0.1", "port": 4096},
}
with open('${vm_dir}/vm-opencode.json', 'w') as f:
    json.dump(opencode_config, f, indent=2)
PYTHON

PROJECT_ROOT="$PROJECT_ROOT" PASSWORD_FILE="$PASSWORD_FILE" "$PYTHON_BIN" << 'PYTHON' > "${vm_dir}/Dockerfile"
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ['PROJECT_ROOT'])

from jinja2 import Environment, FileSystemLoader

templates_dir = Path("workspace/scripts/templates")
password_file_path = os.environ.get('PASSWORD_FILE', '')
password = ''
if password_file_path and os.path.isfile(password_file_path):
    with open(password_file_path) as f:
        password = f.read().strip()
env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    lstrip_blocks=True,
    trim_blocks=True,
)

template = env.get_template("Dockerfile.vm.j2")

context = {
    "security": {
        "purge_sudo": True,
        "no_new_privileges": True,
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "cap_add": [],
    },
    "credentials": {"mode": "none"},
    "ssh": {"mode": "none", "inherit_files": [], "files": []},
    "network": {
        "mode": "bridge",
        "network_name": "workspace-vm-net",
        "policy": "internet",
        "proxy_url": "",
        "whitelist": [],
        "vpn_type": "container",
        "vpn_config": "",
        "vpn_netns": "",
    },
    "traefik_enabled": True,
    "network_enabled": True,
    "openvpn_enabled": False,
    "password": password,
    "certs": ".vms/${vm_name}/certs",
    "vm_install_defaults": ".vms/${vm_name}/install-defaults.yaml",
    "vm_opencode_json": ".vms/${vm_name}/vm-opencode.json",
    "vm_opencode_service": ".vms/${vm_name}/vm-opencode.service",
    "vm_traefik_service": ".vms/${vm_name}/vm-traefik.service",
    "vm_traefik_static": ".vms/${vm_name}/traefik-static.yml",
    "vm_traefik_dynamic": ".vms/${vm_name}/traefik-dynamic.yml",
    "vm_workspace_network_service": ".vms/${vm_name}/vm-workspace-network.service",
    "vm_openvpn_service": "",
    "vm_temp_ssh_key": ".vms/${vm_name}/temp_ssh_key" if os.path.exists(os.path.join(os.environ['PROJECT_ROOT'], ".vms/${vm_name}/temp_ssh_key")) else "",
    "provider": None,
    "web_ui": True,
    "certs_path": "",
    "vpn_config": "",
    "home": "",
    "vm_uuid": "${vm_name}",
}

print(template.render(**context))
PYTHON
