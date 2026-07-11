# OpenVPN Client - Enterprise Requirements Specification

**Document ID:** WS-REQ-OPENVPN-v1.0
**Status:** Draft
**Date:** 2026-07-11
**Classification:** Internal - Enterprise
**Specification:** [SPEC-OPENVPN](SPEC-OPENVPN.md)
**Authors:** Workspace Engineering
**References:**
- [SPEC-OPENVPN](SPEC-OPENVPN.md) (Technical Specification)
- [REQ-BOOT-LAYOUT](REQ-BOOT-LAYOUT.md) (Platform boot directory resolution)
- [SPEC-BOOT-LAYOUT](SPEC-BOOT-LAYOUT.md) (Boot layout implementation)
- [workspace/config/vm-template.yaml](../workspace/config/vm-template.yaml) (VM config reference)
- [workspace/config/bootstrap-components.yaml](../workspace/config/bootstrap-components.yaml) (openvpn bootstrap entry)
- [AGENTS.md](../AGENTS.md) (Universal Agent Rules)

---

## 1. Scope

This document specifies functional and non-functional requirements for **workspace-managed OpenVPN client automation** on the developer host (macOS and Linux) and inside agent VMs created by `make vm`.

The feature provides:

- **Platform-aware binary installation** into `.boot-macos` or `.boot-linux`
- **Persistent host client services**, systemd user unit on Linux, LaunchAgent on macOS
- **CLI control surface**, start, stop, health, status, install-service
- **VM network mode `openvpn`**, container-side client or Linux host netns attach
- **Shared resolution logic**, one module for binary path, config path, validation, health

**In scope:**

- CLI `openvpn` from Homebrew (macOS) or apt (Linux), symlinked into the boot directory
- `.ovpn` client profiles and optional `auth-user-pass` credential files
- Build-time staging of VPN assets into per-VM directories
- Linux `ip netns` setup for `vpn_type: netns`

**Out of scope:**

- OpenVPN Connect GUI / `ovpnagent` / `ovpnhelper` (may coexist on macOS but are not managed)
- OpenVPN server deployment (see DATAOPS `docker-compose.yml` profile `vpn` for OpenVPN-AS)
- VPN inside the podman-machine VM on macOS via host netns (not supported)
- Corporate MDM or system-wide VPN policy enforcement

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Boot Directory** | `.boot-linux` or `.boot-macos`, see REQ-BOOT-LAYOUT |
| **Canonical Config** | `workspace/config/vpn/client.ovpn` (gitignored) |
| **Canonical Auth** | `workspace/config/vpn/auth.txt` (gitignored, optional) |
| **Host Service** | Platform persistence layer: `workspace-openvpn.service` (Linux) or `workspace.openvpn.client` LaunchAgent (macOS) |
| **Container Mode** | `network.mode: openvpn` with `vpn_type: container`, OpenVPN runs inside the agent VM |
| **Netns Mode** | `network.mode: openvpn` with `vpn_type: netns`, VM joins a Linux host network namespace that already runs OpenVPN |
| **Staging** | Copying `.ovpn` / auth files into `.vms/<uuid>/` before `podman build` so Docker COPY paths stay inside the build context |

---

## 3. Functional Requirements

### FR-1: Bootstrap and Binary Resolution

**FR-1.1** The `openvpn` bootstrap component SHALL install the platform OpenVPN client and symlink it to `<boot-dir>/bin/openvpn`.

**FR-1.2** On macOS, bootstrap SHALL use Homebrew (`brew install openvpn`) and SHALL fail with an specific error when Homebrew is missing.

**FR-1.3** On Linux, bootstrap SHALL use `apt-get install openvpn` and SHALL require operator `sudo` for package installation.

**FR-1.4** All runtime consumers (CLI, service units, netns setup) SHALL resolve the binary from `<boot-dir>/bin/openvpn` first, then `PATH`, and SHALL fail explicitly when neither is available.

### FR-2: Configuration Resolution

**FR-2.1** The canonical client config path SHALL be `workspace/config/vpn/client.ovpn`.

**FR-2.2** The canonical optional auth path SHALL be `workspace/config/vpn/auth.txt`.

**FR-2.3** Resolution order for config SHALL be: explicit CLI/VM path → `OPENVPN_CONFIG_FILE` env → canonical path.

**FR-2.4** Resolution order for auth SHALL be: explicit path → `OPENVPN_AUTH_FILE` env → canonical path (optional, omit `--auth-user-pass` when absent).

**FR-2.5** `workspace/config/vpn/` SHALL be gitignored; only a `.gitkeep` placeholder MAY be committed.

**FR-2.6** Config validation SHALL require at least one of `remote `, `proto `, or `dev ` in the file body before start or image build.

### FR-3: Host Client Service

**FR-3.1** Linux SHALL deploy a systemd **user** unit at `~/.config/systemd/user/workspace-openvpn.service`.

**FR-3.2** macOS SHALL deploy a LaunchAgent at `~/Library/LaunchAgents/workspace.openvpn.client.plist`.

**FR-3.3** Service install SHALL be idempotent and SHALL NOT auto-start when canonical config is missing.

**FR-3.4** `vpn --action install-service` SHALL render and install the platform service unit from Jinja templates.

**FR-3.5** `vpn --action start --daemon` SHALL start via the platform service manager (`systemctl --user` / `launchctl`).

**FR-3.6** `vpn --action stop` SHALL stop the platform service.

**FR-3.7** Linux managed-service inventory SHALL register `workspace-openvpn` in `ansible/inventory/host_vars/localhost.yml` under `local_services` for status TUI orphan detection.

### FR-4: Host Health and Status

**FR-4.1** `vpn --action health` SHALL emit JSON: `{"status": "connected"|"disconnected", "connected": bool}`.

**FR-4.2** Connected SHALL require both: (a) a running process whose command line matches the workspace boot-dir binary, and (b) an active tunnel interface (`utun` on Darwin, `tun0` on Linux).

**FR-4.3** Health checks SHALL NOT treat OpenVPN Connect agent processes as workspace VPN connectivity.

**FR-4.4** `vpn --action status` SHALL print resolved binary path, config path, and connection state.

### FR-5: VM Schema

**FR-5.1** `VMNetworkConfig` SHALL support `mode: openvpn` with `vpn_type: container | netns`.

**FR-5.2** Container mode SHALL require `vpn_config` (path to `.ovpn` on the host).

**FR-5.3** Netns mode SHALL require `vpn_netns` (namespace name at `/run/netns/<name>` on Linux).

**FR-5.4** Optional field `vpn_auth` SHALL hold a host path to an auth-user-pass file for container and netns modes.

**FR-5.5** When `mode: openvpn` and `vpn_type: container`, `VMConfig` validation SHALL auto-append `openvpn` to `components` if not already present.

**FR-5.6** When `vpn_type: netns` on Darwin, config validation SHALL fail with a dedicated error, netns attach is Linux-host only.

### FR-6: VM Build and Runtime (Container Mode)

**FR-6.1** Before image build, the pipeline SHALL stage `vpn_config` → `.vms/<uuid>/client.ovpn` and optional `vpn_auth` → `.vms/<uuid>/auth.txt`.

**FR-6.2** Dockerfile generation SHALL COPY staged files to `/etc/openvpn/client.ovpn` and `/etc/openvpn/auth.txt` when present.

**FR-6.3** Build context SHALL include repo-relative staged paths for Jinja `COPY` directives.

**FR-6.4** Container `openvpn.service` SHALL use `{{ container_install_root }}/.boot-linux/bin/openvpn` (currently `/opt/workspace/.boot-linux/bin/openvpn`).

**FR-6.5** Container `openvpn.service` SHALL start after `network-online.target` and before `workspace-network.service` and `opencode.service`.

**FR-6.6** Podman run flags SHALL include `--device /dev/net/tun`, bridge network, and `NET_ADMIN` for container mode.

**FR-6.7** `openvpn.service` SHALL be enabled in the image when container mode is active.

### FR-7: VM Runtime (Netns Mode, Linux Only)

**FR-7.1** Before `podman run`, the pipeline SHALL ensure the named netns exists and OpenVPN is running inside it.

**FR-7.2** Netns setup SHALL: create namespace (idempotent), bring `lo` up, start boot-dir `openvpn --daemon` inside the namespace, verify `tun0` inside the namespace.

**FR-7.3** Netns setup SHALL require `sudo` for `ip netns` and SHALL fail with an specific error when sudo is unavailable.

**FR-7.4** Podman SHALL use `--network ns:/run/netns/<vpn_netns>` with no extra `NET_ADMIN` or `tun` device for netns mode.

### FR-8: Shared Module

**FR-8.1** `workspace/cli/vpn_core.py` SHALL be the single source of shared logic for binary/config resolution, validation, health, and argv construction.

**FR-8.2** `workspace/scripts/bin/run_openvpn_client.py` SHALL delegate to `vpn_core` and SHALL NOT duplicate resolution logic.

**FR-8.3** `workspace/cli/vpn_netns.py` SHALL use `vpn_core` for binary and config resolution.

---

## 4. Non-Functional Requirements

**NFR-1** No silent fallbacks, missing binary, config, or sudo SHALL surface errors to the caller.

**NFR-2** No `dict[str, object]` in new Python code; use typed models and TypedDict where needed.

**NFR-3** Shell scripts SHALL use `#!/bin/bash`, `set -euo pipefail`, and `source ... || exit 1`, per AGENTS.md Rule 14.

**NFR-4** All new source files (non-markdown) SHALL remain under 512 lines.

**NFR-5** Every test SHALL exercise the function it claims to cover; platform branches SHALL have unit tests with mocked subprocess.

**NFR-6** Legacy duplicate `workspace/scripts/ami/scripts/bin/run_openvpn_client.py` SHALL be deleted once the new CLI lands.

---

## 5. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | Bootstrap produces `<boot-dir>/bin/openvpn` on macOS and Linux |
| AC-2 | `vpn --action install-service` installs the correct platform unit without starting when config is absent |
| AC-3 | `vpn --action health` returns `connected: true` only when workspace CLI openvpn is running with tunnel up |
| AC-4 | `make vm` with container openvpn mode builds an image containing `/etc/openvpn/client.ovpn` and enabled `openvpn.service` |
| AC-5 | Container `ExecStart` uses `/opt/workspace/.boot-linux/bin/openvpn`, not `/opt/ami-agents/...` |
| AC-6 | `make vm` with netns mode on Linux pre-creates netns and attaches container |
| AC-7 | Netns VM config on Darwin fails at validation time |
| AC-8 | Unit test coverage gate passes (≥90% workspace threshold) |

---

## 6. Traceability

| Requirement | Spec section | Primary artifact |
|-------------|--------------|------------------|
| FR-1 | SPEC §2 Bootstrap | `bootstrap_openvpn.sh` |
| FR-2 | SPEC §3 Config | `vpn_core.py` |
| FR-3 | SPEC §4 Host service | `bootstrap_openvpn_service.sh`, templates |
| FR-4 | SPEC §5 CLI | `run_openvpn_client.py` |
| FR-5 | SPEC §6 VM schema | `workspace/types/vm.py` |
| FR-6 | SPEC §7 VM container | `vm_build.py`, `Dockerfile.vm.j2` |
| FR-7 | SPEC §8 VM netns | `vpn_netns.py`, `setup_vpn_netns.sh` |
| FR-8 | SPEC §3 | `vpn_core.py` |