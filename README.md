# Sovereign Digital Workspace Stack

A federated repository for developing and running web services and AI agents on infrastructure **you control**.

The design centers on **data sovereignty**, **system immutability**, and **workspace-wide compliance**: agents run inside guarded sandboxes, quality gates apply before code ships, and sensitive services stay on your machines rather than a vendor cloud.

Clone the repository and run `make install` to set up the core developer toolchain (uv, OpenCode, Podman, Ansible, and the rest of the bootstrap catalog). For GPU-backed LLM inference, QEMU agent VMs, or a host VPN tunnel, use the matching installer listed under **Getting Started** below. Section 2 covers each subsystem; section 5 covers the contribution contract and quality gates.

---

## 1. Getting Started

### Prerequisites

Before cloning or running workspace installers, confirm your host can support the components you plan to use:

- **Operating system:** Linux (x86_64) or macOS (Apple Silicon or Intel). Most GPU and llama workflows are Linux-first; macOS is supported for general bootstrap and development.
- **Elevated permissions:** `sudo` for system packages (apt/brew), Intel GPU drivers, QEMU firmware, logrotate limits, and optional `git-guard` installation. LLM/GPU prereqs are handled through `make llama-setup`, not the general bootstrap.
- **Boot directory:** `.boot-linux/` on Linux or `.boot-macos/` on macOS. Created and populated when you run `make install` or `make core`; holds vendored binaries (OpenVPN, QEMU pins, and similar) used by CLI extensions. Layout: [`docs/specifications/SPEC-BOOT-LAYOUT.md`](docs/specifications/SPEC-BOOT-LAYOUT.md).

Install base system packages once per host (before or alongside your first workspace installer). `make install`, `make install-ci`, and `make llama-setup` all run `init-check` automatically; run the steps below manually only when you want to resolve apt/brew gaps ahead of time:

```bash
make init-check    # report missing apt/brew packages
sudo make init     # install from config/system-deps.yaml + privileged bootstrap
```

Run as root, `make init` also performs the privileged bootstrap (audit 2026-07-18 section 4.6): promotes `projects/CI` from `projects/WORKSPACE-CI` via `deploy-ci`, installs the git guard, root-locks hooks and exemption files in every consumer repo, and enforces syslog limits. It fails loudly if `projects/WORKSPACE-CI` is missing; clone it first with non-root `make ensure-repos`.

### Installation paths

Choose the installer that matches what you are setting up. Each path has its own interactive TUI, CI-friendly non-interactive variant, and linked documentation.

- **General development tools** (`uv`, OpenCode, Podman, Ansible, and the rest of the bootstrap catalog):  
  `make install` (interactive TUI). Component list: [`workspace/config/bootstrap-components.yaml`](workspace/config/bootstrap-components.yaml)

- **CI / unattended bootstrap** (same components, fixed defaults):  
  `make install-ci`. Config: [`workspace/config/install-defaults.yaml`](workspace/config/install-defaults.yaml)

- **LLM inference, Intel GPU, Vulkan, llamafile / llama.cpp** (builds, bundles, systemd deploy, diagnostics):  
  `make llama-setup`. Operator guide: [`docs/specifications/SPEC-LLAMA-SETUP-TUI.md`](docs/specifications/SPEC-LLAMA-SETUP-TUI.md).  
  Llama, GPU drivers, and `xpu-smi` are **not** part of `make install`; use this path instead.

- **LLM setup in CI** (non-interactive defaults, no TTY):  
  `make llama-setup-ci`. Defaults: [`workspace/config/llama-setup-defaults.yaml`](workspace/config/llama-setup-defaults.yaml)

- **QEMU hypervisor** (binaries, firmware, cloud-image helpers for `make vm`):  
  `make install-qemu`. Spec: [`docs/specifications/SPEC-VM-HYPERVISOR.md`](docs/specifications/SPEC-VM-HYPERVISOR.md)

- **Host OpenVPN client** (tunnel to remote workspace networks):  
  `make vpn-install`. Spec: [`docs/specifications/SPEC-OPENVPN.md`](docs/specifications/SPEC-OPENVPN.md)

### Quick start (general bootstrap)

```bash
git clone git@github.com:Independent-AI-Labs/WORKSPACE-VM.git && cd WORKSPACE-VM

make install
```

The bootstrap TUI installs selected components from the federated dependency graph. When finished, `ami-oc` (opencode wrapper) is on your PATH.

### Post-install (requires sudo)

```bash
sudo make init
```

Runs the full privileged bootstrap: system packages, `deploy-ci` promotion of `projects/CI`, git guard install, hook + exemption root-locks across consumer repos, and logrotate/journald rate limits on `/var/log/syslog` (INCIDENT-2026-07-05). `make install` and `make install-ci` are strictly non-root; they end by pointing here.

Optional operator steps:

```bash
sudo make guard-up         # idempotent fleet bring-up (provision + guard install)
sudo make guard-refresh    # after pulling guard code
make guard-check           # read-only health
```

---

## 2. Subsystems

Beyond the bootstrap toolchain in §1, WORKSPACE-VM ships four operator-facing capabilities: **on-prem LLM inference**, **isolated agent runtimes**, **secure remote connectivity**, and **reproducible inference benchmarks**. Each subsystem uses the same boot-directory layout, Makefile entrypoints, and quality-gate model as the rest of the workspace.

Diagram nodes use Unicode symbols so they render on GitHub without external icon font packs.

### LLM inference (llamafile / llama.cpp)

WORKSPACE-VM supports **local, sovereign LLM inference** on hardware you control (Intel GPU/SYCL, Vulkan, or CPU), so agent loops and benchmarks never depend on a vendor API. The unified entrypoint is `make llama-setup`, an interactive wizard that detects hardware, installs prerequisites, builds one stack profile, bundles weights, deploys a systemd service (or runs a local binary), and runs diagnostics. Stack profiles live in [`workspace/config/llama-setup.yaml`](workspace/config/llama-setup.yaml); GGUF weights and `.args` manifests live under `models/`. Two engine families are supported: **llamafile** (single portable `.llamafile` binary) and **llama.cpp** (compiled `llama-server` with per-backend flavors).

```bash
make llama-setup
```

```mermaid
%%{init: {'flowchart': {'nodeSpacing': 8, 'rankSpacing': 36, 'padding': 4}, 'themeVariables': {'fontSize': '11px'}}}%%
flowchart TB
  subgraph legend [Legend]
    direction LR
    legTrigger([Trigger]) ~~~ legInput[/Input/] ~~~ legAction[Action] ~~~ legStore[(State)] ~~~ legOngoing(Ongoing)
  end
  classDef legendItem font-size:10px,stroke-width:1px
  class legTrigger,legInput,legAction,legStore,legOngoing legendItem
  style legend fill:transparent,stroke:#ccc,stroke-width:1px

  legOngoing ~~~ operator

  operator(["👤 Operator or automation"])
  launch(["🧠 Run make llama-setup wizard"])

  subgraph diskInputs ["Wizard reads from disk"]
    direction LR
    profileConfig[/"📋 Profile catalog: workspace/config/llama-setup.yaml"/]
    weights[("🗄️ models/: GGUF weights and .args manifests")]
  end

  subgraph llamafileStack ["📦 Llamafile stack: single portable .llamafile binary"]
    direction TB
    bundleLf[Bundle GGUF from models/ into .llamafile]
    deployLf[Install llamafile systemd unit]
    bundleLf --> deployLf
  end

  subgraph llamaCppStack ["⚙️ llama.cpp stack: compiled llama-server per backend"]
    direction TB
    buildCpp[Build llama-server for Vulkan, SYCL, or CPU]
    deployCpp[Install llamaserver systemd unit]
    buildCpp --> deployCpp
  end

  server("🌐 HTTP inference server on host")
  clients(["🔌 HTTP clients"])

  operator --> launch --> diskInputs
  profileConfig -->|llamafile profile| llamafileStack
  profileConfig -->|llama.cpp profile| llamaCppStack
  weights -.->|embed in bundle| bundleLf
  weights -.->|load at deploy| buildCpp
  deployLf --> server
  deployCpp --> server
  server --> clients
```

The wizard runs **one** profile per invocation; the other stack is not built or deployed. The `llamafile_cpu_chat` profile skips systemd deploy and runs as a local binary (see table).

Bundle zipalign detail: [`docs/specifications/SPEC-LLAMAFILE-MINICPM5-1B.md`](docs/specifications/SPEC-LLAMAFILE-MINICPM5-1B.md).

Stack profiles:

| ID | Deploy unit | Port |
| :--- | :--- | :--- |
| `llamafile_vulkan_server` | `llamafile-<model>` | 8765 |
| `llama_cpp_vulkan` | `llamaserver@vulkan` | 8080 |
| `llama_cpp_sycl` | `llamaserver@sycl` | 8082 |
| `llama_cpp_cpu` | `llamaserver@cpu` | 8081 |
| `llamafile_cpu_chat` | none (local binary) | n/a |

Escape hatches (scripting / CI):

```bash
make -f Makefile.llamafile help
make -f Makefile.llamaserver help
```

Specs: [`docs/specifications/SPEC-LLAMA-SETUP-TUI.md`](docs/specifications/SPEC-LLAMA-SETUP-TUI.md), [`docs/specifications/SPEC-LLAMAFILE-MINICPM5-1B.md`](docs/specifications/SPEC-LLAMAFILE-MINICPM5-1B.md)

### Agent VMs (`make vm`)

**Agent VMs** are isolated Linux environments where AI coding agents (OpenCode, Cursor-class tools, and similar) execute workloads without direct access to the host kernel or writable access to the host workspace tree. `make vm` provisions a per-agent sandbox from a single YAML settings file ([`workspace/config/vm-template.yaml`](workspace/config/vm-template.yaml)); lifecycle state persists under `.vms/<uuid>/` on the host for day-2 start, stop, shell, and exec commands. The default backend is **rootless Podman**: fast to spin up and air-gapped by default. **QEMU** adds a full hardware VM boundary when you need host-kernel isolation or authoritative WORKSPACE-GUARD capability testing.

```mermaid
%%{init: {'flowchart': {'nodeSpacing': 8, 'rankSpacing': 36, 'padding': 4}, 'themeVariables': {'fontSize': '11px'}}}%%
flowchart TB
  subgraph legend [Legend]
    direction LR
    legTrigger([Trigger]) ~~~ legInput[/Input/] ~~~ legAction[Action] ~~~ legStore[(State)] ~~~ legOngoing(Ongoing)
  end
  classDef legendItem font-size:10px,stroke-width:1px
  class legTrigger,legInput,legAction,legStore,legOngoing legendItem
  style legend fill:transparent,stroke:#ccc,stroke-width:1px

  legOngoing ~~~ operator

  operator(["👤 Operator or automation"])
  launch[/"🤖 Run make vm with a config file"/]

  subgraph diskInputs ["Wizard reads from disk"]
    direction LR
    settings[/"📄 VM settings YAML: workspace/config/vm-template.yaml"/]
    hostWorkspace[("🗄️ Host workspace repo on disk")]
  end

  subgraph podmanPath ["🐳 Podman: container shares host kernel"]
    direction TB
    buildImage[Bake toolchain into image via install-ci]
    seedVolume[Seed /workspace volume from host paths]
    runContainer[Start container with named volumes]
    buildImage --> seedVolume --> runContainer
  end

  subgraph qemuPath ["🖥️ QEMU: guest runs its own Linux kernel"]
    direction TB
    overlayDisk[Create per-VM QCOW2 overlay from base image]
    bootGuest[Boot guest: virtio-9p RO repo share + SSH on localhost]
    provisionGuest[SSH provision: rsync subset to /opt/workspace, install-ci]
    overlayDisk --> bootGuest --> provisionGuest
  end

  persisted[("🗄️ Per-VM state under .vms on host")]
  dayTwo("🤖 Day-2: start, stop, shell, exec")

  operator --> launch --> diskInputs
  settings -->|Podman default| podmanPath
  settings -->|QEMU| qemuPath
  hostWorkspace -.->|files, sync, RO binds| seedVolume
  hostWorkspace -.->|virtio-9p read-only| bootGuest
  hostWorkspace -.->|rsync on provision| provisionGuest
  podmanPath --> persisted
  qemuPath --> persisted
  persisted --> dayTwo
```

Pick **Podman** for everyday agent development (seconds to boot, rootless, default `network.mode: none`). Pick **QEMU** when the guest must have its own kernel so host guardrails cannot be bypassed, or when running authoritative guard E2E (`make test-e2e-qemu-full`). Module map: [`docs/specifications/SPEC-VM-HYPERVISOR.md#1-architecture`](docs/specifications/SPEC-VM-HYPERVISOR.md#1-architecture).

**Workspace sharing:** both backends copy host workspace content into an isolated writable tree; neither mounts the host repo writable.

- **Podman** ([`vm_build.py`](workspace/cli/vm_build.py), [`vm_sync.py`](workspace/cli/vm_sync.py)): `files:` pre-copies host paths into the `<uuid>-workspace` volume at create; `make vm sync` rsyncs per `sync:` rules; optional read-only `mounts:` bind host paths into the container. Agent writes go to `/workspace` inside the volume.
- **QEMU** ([`qemu_provision.py`](workspace/cli/hypervisor/qemu_provision.py)): host repo is virtio-9p **read-only** at `/mnt/workspace-ro`; provision rsyncs a profile-selected subset to `/opt/workspace` on the guest QCOW2, then runs `install-ci`. Host tree is never written by the guest.

Podman shares the host kernel, so a named volume plus copy/sync is enough. QEMU runs a separate kernel and cannot use Podman volumes: virtio-9p exposes the host tree read-only, then rsync creates a writable guest-disk copy.

| `provision` | Rsync scope (QEMU) |
| :--- | :--- |
| `poc` | Workspace core layout only |
| `guard` | Skeleton + `projects/CI/` + `projects/WORKSPACE-GUARD/` |
| `full-ci` | Skeleton + entire `projects/` |

**Day-2 commands:** `vm rebuild` and `make vm sync` are Podman-only. QEMU provision runs once at create.

**Podman network** ([`vm_build.py`](workspace/cli/vm_build.py)): default `network.mode: none` (`--network none`). `NET_ADMIN` is added only for bridge + `internet`/`proxy` policy, or OpenVPN with `vpn_type: container`. QEMU POC defers most network modes.

**Guard E2E:** authoritative capability tests run inside a provisioned QEMU guest (`make test-e2e-qemu-full`, `make test-authoritative`). See [`docs/specifications/SPEC-VM-HYPERVISOR.md` section 12](docs/specifications/SPEC-VM-HYPERVISOR.md#12-workspace-guard-integration).

```bash
make install-qemu          # once per host (QEMU + genisoimage + cloud-localds)
make vm CONFIG=path/to/vm.yaml
make vm-list
make test-e2e-qemu         # guard E2E in QEMU guest
```

Specs: [`docs/requirements/REQ-VM-HYPERVISOR.md`](docs/requirements/REQ-VM-HYPERVISOR.md), [`docs/specifications/SPEC-VM-HYPERVISOR.md`](docs/specifications/SPEC-VM-HYPERVISOR.md)

### Host VPN

When workspace services (DATAOPS Postgres, Keycloak, staging networks) run on a remote host, WORKSPACE-VM installs a **boot-directory OpenVPN client** so your machine joins that network without the commercial OpenVPN Connect app. Automation spans three layers documented in [`docs/specifications/SPEC-OPENVPN.md`](docs/specifications/SPEC-OPENVPN.md): bootstrap the binary into `.boot-linux/` or `.boot-macos/`, run a persistent host tunnel (`make vpn-start`), and optionally attach VPN routing to agent VMs or containers that need egress through the tunnel.

```mermaid
flowchart LR
  operator(["👤 Operator"])
  install(["🔒 make vpn-install"])
  hostSvc(["🌐 Host tunnel"])
  vmNet(["🤖 Agent VM egress"])
  remote(["🗄️ Remote workspace network"])
  operator --> install --> hostSvc --> remote
  hostSvc -.-> vmNet --> remote
```

```bash
make vpn-install
make vpn-start             # PERSIST=1 for reboot auto-start
make vpn-status
```

Full architecture: [`docs/specifications/SPEC-OPENVPN.md#architecture`](docs/specifications/SPEC-OPENVPN.md#architecture)

### Benchmarks

Config-driven benchmarks under `benchmarks/` measure inference quality and latency on **your** stack, not a cloud API baseline. The flagship **transcript classifier** replays real OpenCode SQLite sessions turn-by-turn against a running llamafile server, simulating a rolling-window moderator with KV-cache reuse (`id_slot` + `cache_prompt`). Use it to regression-test model and server changes before agents depend on them.

Requires a server up first (`make llama-setup` or `make -f Makefile.llamafile install-llamafile`):

```bash
make -f Makefile.llamafile benchmark-llamafile-transcript-classifier
```

README: [`benchmarks/llamafile/transcript_classifier/README.md`](benchmarks/llamafile/transcript_classifier/README.md)

---

## 3. Workspace Philosophy

WORKSPACE-VM is an **umbrella repo** that orchestrates multiple independent git clones under `projects/` ([`workspace/config/workspace-clones.yaml`](workspace/config/workspace-clones.yaml)). `projects/CI` and `projects/DATAOPS` are mandatory; other projects (PORTAL, TRADING, GUARD, etc.) opt in via `bootstrap-repos`. Agents, hooks, and guard policy apply workspace-wide; compliance is not optional per nested repo.

- **Fail-Closed Security:** Agent VMs default to air-gapped Podman (`network.mode: none`). `git-guard` wraps `/usr/bin/git` at the syscall boundary, blocking `--no-verify` and history rewrite. `podman-guard` enforces container egress and capability policy before a container starts.
- **Compliance as Code:** WORKSPACE-CI (`projects/CI/`) generates native git hooks from `.pre-commit-config.yaml` and installs them recursively across nested repos. Hook stages and checks: [`projects/CI/README.md`](projects/CI/README.md).
- **Topological Orchestration:** Prefer `moon` tasks for cross-repo builds and tests. Resync clones with `moon run :update`.

---

## 4. Navigation Map

Use this table as a route map when onboarding. It shows where agent logic, enforcement, infrastructure, model weights, and specifications live relative to the umbrella root.

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

## 5. Contribution Contract

Quality gates are mandatory and, when WORKSPACE-GUARD is installed, enforced at the git syscall boundary. There is no `--no-verify` escape hatch. Before opening a PR:

1. **Pass the contract:** `make contract-check` (Makefile targets) and `make check` (lint + type-check + test via moon). Run `make check-push` locally to mirror the pre-push gate.
2. **Install hooks:** `make install-hooks` (or `make install`, which runs `install-hooks-recursive` across the workspace and nested `projects/*` repos). Hooks are mandatory; there is no `--no-verify` escape when git-guard is installed.
3. **Understand the gates:** WORKSPACE-CI enforces three hook stages from [`projects/CI/`](projects/CI/):
   - **pre-commit**: ruff format/lint, mypy, gitleaks, banned-word and error-swallow scans, file-length limits, dependency freshness, unstaged-change guard.
   - **commit-msg**: conventional message format (`type: description` + body); blocks agent attribution patterns.
   - **pre-push**: `make check-push`, coverage thresholds, co-authored history scan.
4. **Align history:** No rebase/amend on pushed commits; git-guard enforces this at the syscall boundary.
5. **Documentation:** New specs live under `docs/` or the project's `docs/` subdirectory.

Full doc index: [`docs/README.md`](docs/README.md)
