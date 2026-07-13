# Sovereign AI Workspace

**WORKSPACE-VM** is a federated, hard-walled workspace for developing and running AI agents on infrastructure you control. The design centers on **data sovereignty**, **system immutability**, and **workspace-wide compliance**: agents run inside guarded sandboxes, quality gates apply before code ships, and sensitive services stay on your machines rather than a vendor cloud.

You do not install everything with one command. Bootstrap, LLM/GPU setup, VM hypervisors, and VPN each have their own entrypoint and documentation. Pick the workflow below that matches what you are trying to do, then follow its guide. The sections later in this README cover VMs, inference, VPN, and benchmarks in more detail.

---

## 1. Getting Started

### Prerequisites

Before cloning or running workspace installers, confirm your host can support the components you plan to use:

- **Operating system:** Linux (x86_64) or macOS (Apple Silicon or Intel). Most GPU and llama workflows are Linux-first; macOS is supported for general bootstrap and development.
- **Elevated permissions:** `sudo` for system packages (apt/brew), Intel GPU drivers, QEMU firmware, logrotate limits, and optional `git-guard` installation. LLM/GPU prereqs are handled through `make llama-setup`, not the general bootstrap.
- **Boot directory:** `.boot-linux/` on Linux or `.boot-macos/` on macOS. Created and populated when you run `make install` or `make core`; holds vendored binaries (OpenVPN, QEMU pins, and similar) used by CLI extensions.

Check and install base system dependencies before workspace component installers:

```bash
make init-check    # report missing apt/brew packages
sudo make init     # install from config/system-deps.yaml
```

### Installation paths

Each major capability has a dedicated installer. They are intentionally separate so you only pull in what you need and so CI can run non-interactive variants without a TTY.

- **General development tools** (`uv`, OpenCode, Podman, Ansible, and the rest of the bootstrap catalog):  
  `make install` (interactive TUI). Component list: [`workspace/config/bootstrap-components.yaml`](workspace/config/bootstrap-components.yaml)

- **CI / unattended bootstrap** (same components, fixed defaults):  
  `make install-ci`. Config: [`workspace/config/install-defaults.yaml`](workspace/config/install-defaults.yaml)

- **LLM inference, Intel GPU, Vulkan, llamafile / llama.cpp** (builds, bundles, systemd deploy, diagnostics):  
  `make llama-setup`. Operator guide: [`docs/SPEC-LLAMA-SETUP-TUI.md`](docs/SPEC-LLAMA-SETUP-TUI.md).  
  Llama, GPU drivers, and `xpu-smi` are **not** part of `make install`; use this path instead.

- **LLM setup in CI** (non-interactive defaults, no TTY):  
  `make llama-setup-ci`. Defaults: [`workspace/config/llama-setup-defaults.yaml`](workspace/config/llama-setup-defaults.yaml)

- **QEMU hypervisor** (binaries, firmware, cloud-image helpers for `make vm`):  
  `make install-qemu`. Spec: [`docs/SPEC-VM-HYPERVISOR.md`](docs/SPEC-VM-HYPERVISOR.md)

- **Host OpenVPN client** (tunnel to remote workspace networks):  
  `make vpn-install`. Spec: [`docs/SPEC-OPENVPN.md`](docs/SPEC-OPENVPN.md)

### Quick start (general bootstrap)

```bash
git clone git@github.com:Independent-AI-Labs/WORKSPACE-VM.git && cd WORKSPACE-VM

make install
```

The bootstrap TUI installs selected components from the federated dependency graph. When finished, `ami-oc` (opencode wrapper) is on your PATH.

### Post-install (requires sudo)

```bash
make enforce-syslog-limits
```

Configures logrotate and journald rate limits on `/var/log/syslog` (see incident 2026-07-05 in repo history).

Optional operator steps:

```bash
sudo make build-guard      # build git-guard (SSH agent forwarded under sudo automatically)
sudo make install-guard    # install git-guard to /usr/bin/git
```

---

## 2. Subsystems

### LLM inference (llamafile / llama.cpp)

Recommended entrypoint:

```bash
make llama-setup
```

Guides Intel drivers, Vulkan dev, engine/DSO builds, `.llamafile` bundles, and optional systemd deploy (`llamafile-<model>` / `llamaserver@<flavor>`).

Escape hatches (scripting / CI):

```bash
make -f Makefile.llamafile help
make -f Makefile.llamaserver help
```

Specs: [`docs/SPEC-LLAMA-SETUP-TUI.md`](docs/SPEC-LLAMA-SETUP-TUI.md), [`docs/SPEC-LLAMAFILE-MINICPM5-1B.md`](docs/SPEC-LLAMAFILE-MINICPM5-1B.md)

### Agent VMs (`make vm`)

Dual isolation backends: **Podman** (default) and **QEMU** (`isolation.backend: qemu` in VM config).

```bash
make install-qemu          # once per host (QEMU + genisoimage + cloud-localds)
make vm CONFIG=path/to/vm.yaml
make vm-list
make test-e2e-qemu         # guard E2E in QEMU guest
```

Specs: [`docs/REQ-VM-HYPERVISOR.md`](docs/REQ-VM-HYPERVISOR.md), [`docs/SPEC-VM-HYPERVISOR.md`](docs/SPEC-VM-HYPERVISOR.md), [`docs/TRACK-VM-HYPERVISOR.md`](docs/TRACK-VM-HYPERVISOR.md)

### Host VPN

```bash
make vpn-install
make vpn-start             # PERSIST=1 for reboot auto-start
make vpn-status
```

Spec: [`docs/SPEC-OPENVPN.md`](docs/SPEC-OPENVPN.md)

### Benchmarks

Llamafile transcript classifier (rolling 32K window, KV cache reuse):

```bash
# Server must be running first (make llama-setup or make install-llamafile)
make -f Makefile.llamafile benchmark-llamafile-transcript-classifier
```

README: [`benchmarks/llamafile/transcript_classifier/README.md`](benchmarks/llamafile/transcript_classifier/README.md)

---

## 3. Workspace Philosophy

This workspace is not a standard monorepo; it is a **federated system**.

- **Fail-Closed Security:** Interactions are gated by `git-guard` (immutability) and `podman-guard` (network/FS isolation).
- **Compliance as Code:** The `WORKSPACE-CI` contract enforces strict quality gates (hooks, coverage, linting) on every sub-project.
- **Topological Orchestration:** Use `moon` to manage the dependency graph. Prefer `moon` tasks over manual sub-project commands.

---

## 4. Navigation Map

| Purpose | Path | Description |
| :--- | :--- | :--- |
| **Core Agents** | `workspace/` | Agent logic, CLI entrypoints, provider handlers. |
| **Workspace CI** | `projects/CI/` | Enforcement engine, system-deps resolver, native hooks. |
| **Data/Infra** | `projects/DATAOPS/` | Sovereign services (Postgres, Keycloak, Vaultwarden). |
| **Orchestration** | `projects/` | Federated projects (TRADING, SRP, PORTAL, etc.). |
| **LLM models** | `models/` | GGUF weights and `.args` manifests for llamafile bundles. |
| **LLM setup scripts** | `scripts/setup/` | Build, GPU probe, Intel/Vulkan prereqs, Ansible wrappers. |
| **Benchmarks** | `benchmarks/` | Config-driven inference benchmarks. |
| **Workspace docs** | `docs/` | REQ/SPEC/TRACK documents (indexed in [`docs/README.md`](docs/README.md)). |
| **Subsystem specs** | `projects/*/docs/` | Per-project requirements. |

---

## 5. Common Failure Modes & Troubleshooting

1. **"Operation not permitted" on `git`:**
   - **Reason:** `git-guard` immutable bit on binaries.
   - **Fix:** `sudo projects/WORKSPACE-GUARD/scripts/bootstrap_git_guard.sh --uninstall` for maintenance only.

2. **Podman / container failures:**
   - **Fix:** `make -C projects/DATAOPS runtime-down` then `runtime-up`.

3. **Bootstrap drift:**
   - **Fix:** `moon run :update` to resync the workspace graph.

4. **Root disk filling (`/var/log/syslog`):**
   - **Fix:** `make enforce-syslog-limits`, then `journalctl --user -u <service> --since '5 min ago'`.

5. **QEMU / cloud-init tests skipped:**
   - **Reason:** `genisoimage` or `cloud-localds` missing on host.
   - **Fix:** `sudo make install-qemu`.

6. **Vulkan GPU probe fails / llamafile won't use GPU:**
   - **Reason:** Not in `render`/`video` groups, or `vulkaninfo` missing.
   - **Fix:** `make llama-setup` prereq phase (or `sudo bash scripts/setup/install-intel-gpu.sh --drivers`), then `newgrp render`.

7. **`sudo make build-guard` hangs on git clone:**
   - **Fix:** Should not happen; bootstrap-repos reconstructs `SSH_AUTH_SOCK` under sudo. Ensure your SSH agent is loaded before sudo.

---

## 6. Contribution Contract

Before opening a PR:

1. **Pass the contract:** `make contract-check` (or `make check`).
2. **Align history:** No rebase/amend on pushed commits; git-guard enforces this.
3. **Documentation:** New specs live under `docs/` or the project's `docs/` subdirectory.

Full doc index: [`docs/README.md`](docs/README.md)