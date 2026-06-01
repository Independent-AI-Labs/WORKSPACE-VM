# AMI-AGENTS V3 — Complete Migration Plan

**Document ID:** AMI-MIGRATION-V3-v1.0
**Status:** Final
**Date:** 2026-06-01
**Author:** AMI-Agents Engineering

---

## Table of Contents

1. [Scope & Context](#1-scope-context)
2. [Archive Strategy](#2-archive-strategy)
3. [Code Deletions](#3-code-deletions)
4. [Replacement Architecture](#4-replacement-architecture)
5. [Docker Virtualisation Stack](#5-docker-virtualisation-stack)
6. [Traefik HTTPS with Client Certificate Authentication](#6-traefik-https-with-client-certificate-authentication)
7. [Ansible Orchestration](#7-ansible-orchestration)
8. [Bootstrapping & Installation](#8-bootstrapping-installation)
9. [Migration Phases](#9-migration-phases)
10. [Verification](#10-verification)
11. [Risk Register](#11-risk-register)
12. [Appendix: File Inventory](#12-appendix-file-inventory)

---

## 1. Scope & Context

### 1.1 What AMI-AGENTS Is Today

AMI-AGENTS is a federated AI-agent workspace with:
- **Python agent orchestration layer** — `ami/` package (CLI entrypoints, provider routing, transcript storage, bootloader agent, TUI components)
- **Three proprietary CLI agents** installed via npm: `@anthropic-ai/claude-code`, `@google/gemini-cli`, `@qwen-code/qwen-code` (in `scripts/package.json`)
- **Custom Python CLI/TUI** — `ami/cli/` (claude_cli.py, gemini_cli.py, qwen_cli.py), `ami/cli_components/` (dialogs, text editor, status, containers), `ami/core/` (bootloader agent, conversation, guards)
- **Existing opencode source clone** at `projects/opencode/` (anomalyco/opencode `dev` branch, full git history)
- **Container specification** (DRAFT) — `docs/specifications/SPEC-AGENT-CONTAINERS.md` plans container isolation
- **Docker infrastructure** — AMI-DATAOPS compose stack (postgres, redis, dgraph, mongo, keycloak, vaultwarden, prometheus, searxng) — no reverse proxy
- **Ansible** — llamaserver deployment playbooks
- **CI/quality** — AMI-CI enforcement, pre-commit hooks, RUST-GUARD git immutability

### 1.2 What Changes

| Component | Current State | Target State |
|-----------|--------------|--------------|
| Agent CLI runtime | Claude Code + Gemini + Qwen (npm) | **opencode-ai only** (npm) |
| Python agent orchestration | `ami/cli/`, `ami/core/`, `ami/cli_components/`, `ami/types/`, `ami/tools/` | **Archived** — all agent orchestration delegated to opencode |
| Agent CLI wrappers | `claude_cli.py`, `gemini_cli.py`, `qwen_cli.py` | **Deleted** |
| CLI version manager | `update_cli_versions.py` | **Deleted** — opencode-ai version managed via npm |
| Agent bootstrap | `bootstrap_agents.sh` (installs 3 CLIs) | **Replaced** — installs `opencode-ai` only |
| Shell extensions | `extension_registry.py`, custom `ami-*` commands | **Replaced** — aliases to `opencode` |
| Docs archive | Active requirements, research, specs for A2A | **Moved** to `docs/archive/v2/` |
| Container spec | DRAFT SPEC-AGENT-CONTAINERS.md | **Superseded** by this plan's Dockerisation |
| Reverse proxy | **None** | **Traefik** with mutual TLS |
| opencode web UI | Not configured | **Enabled** on `127.0.0.1:4096` inside container |

### 1.3 What Stays

| Component | Reason |
|-----------|--------|
| `projects/opencode/` | **Source clone** — continues as the development branch for opencode itself |
| `projects/AMI-DATAOPS/` | Data infrastructure (postgres, keycloak, etc.) — independent of agent choice |
| `projects/AMI-CI/` | CI enforcement — independent of agent choice |
| `projects/RUST-GUARD/` | Git immutability — security infrastructure |
| `ami/config/` | Configuration (automation, bootstrap components, hooks) — still used by Makefile |
| `ami/scripts/bootstrap/` | System tool bootstrapping (uv, python, rust, podman, moon, etc.) — independent |
| `ami/scripts/pre-req.sh` | System pre-requisites — still needed |
| `ami/scripts/shell/` | Shell setup — ported to use `opencode` instead of 3 agents |
| `ansible/` | Deployment automation — expanded |
| `Makefile` | Build orchestration — target names mostly stay, implementations change |
| `.pre-commit-config.yaml` | Quality gates — unchanged |
| `pyproject.toml` | Python package — `ami` package tree stays for CI/config scripts |

---

## 2. Archive Strategy

### 2.1 Archive Location

All pre-V3 material moves to `docs/archive/v2/`:

```
docs/archive/v2/
├── AGENTS.md                    # Old agent rules (replaced by V3 rules)
├── ARCH-AGENT-ECOSYSTEM.md      # Superseded architecture
├── AUDIT-CLAUDE-SESSION-*.md    # Old audits
├── AUDIT-INSTALL-ISSUES.md      # Old audits
├── DEPENDENCY-MAP.md            # Old map
├── EXTENSIONS.md                # Old extension spec
├── GUIDE-USAGE.md               # Old usage guide
├── README.md                    # Old docs readme
├── VULKAN-SWA-PROMPT-PROCESSING-BUG.md  # Old bug report
├── requirements/                # Old requirements (REQ-AGENT-CONTAINERS, REQ-EXTENSIONS, etc.)
├── specifications/              # Old specs (SPEC-AGENT-CONTAINERS, SPEC-EXTENSIONS, etc.)
├── architecture/                # Old architecture proposals
├── research/                    # Research programme (WS-1 through WS-7, EXECUTIVE-SUMMARY)
└── archive/                     # Old archive (previously at docs/archive/)
```

### 2.2 What Moves vs Deletes

| Action | Items |
|--------|-------|
| **Archive** (move to `docs/archive/v2/`) | All doc files in `docs/` except `REQUIREMENTS-A2A.md`, `GAP-ANALYSIS-A2A.md`, and this plan |
| **Delete** | All Python agent orchestration code: `ami/cli/`, `ami/core/`, `ami/cli_components/`, `ami/types/`, `ami/tools/` |
| **Delete** | `scripts/package.json` (claude, gemini, qwen deps) |
| **Delete** | `scripts/setup/node.sh` |
| **Delete** | `ami/tools/update_cli_versions.py` |
| **Delete** | `ami/scripts/bootstrap/bootstrap_agents.sh` |
| **Rewrite** | `README.md` — point to opencode-ai as primary agent |
| **Rewrite** | `AGENTS.md` — V3 rules (opencode-focused, no claude/gemini/qwen) |

---

## 3. Code Deletions

### 3.1 Python Agent Orchestration (Entirely Replaced by opencode-ai)

The Python agent layer was a full custom agent runtime. Every file below is **deleted** because opencode-ai handles all of this:

```
ami/cli/                           # Custom CLI entrypoints
  ├── base_provider.py             # Provider abstraction
  ├── claude_cli.py                # Claude Code CLI wrapper
  ├── gemini_cli.py                # Gemini CLI wrapper
  ├── qwen_cli.py                  # Qwen CLI wrapper
  ├── factory.py                   # Agent factory
  ├── interface.py                 # Agent interface
  ├── main.py                      # CLI main
  ├── mode_handlers.py             # Mode routing
  ├── process_utils.py             # Process management
  ├── provider_type.py             # Provider types
  ├── streaming.py                 # Output streaming
  ├── streaming_utils.py           # Streaming utilities
  ├── stream_processor.py          # Stream processing
  ├── timer_utils.py               # Timer utilities
  ├── transcript_search.py         # Transcript search
  ├── transcript_store.py          # Transcript storage
  ├── validation_utils.py          # Validation
  ├── editor_utils.py              # Editor utilities
  ├── env_utils.py                 # Environment utilities
  ├── exec_utils.py                # Execution utilities
  ├── exceptions.py                # Exceptions
  ├── config.py                    # CLI config
  ├── constants.py                 # Constants
  └── __init__.py

ami/core/                          # Agent core
  ├── bootloader_agent.py          # Bootloader agent
  ├── config.py                    # Core config
  ├── constants.py                 # Constants
  ├── conversation.py              # Conversation management
  ├── env.py                       # Environment
  ├── factory.py                   # Agent factory
  ├── guards.py                    # Safety guards
  ├── interfaces.py                # Interfaces
  ├── logic.py                     # Agent logic
  ├── models.py                    # Data models
  ├── utils.py                     # Utilities
  ├── policies/                    # Policy enforcers
  └── __init__.py

ami/cli_components/                # TUI components
  ├── confirmation_dialog.py       # Confirmation UI
  ├── cursor_manager.py            # Cursor management
  ├── dialogs.py                   # Dialog system
  ├── editor_display.py            # Editor display
  ├── editor_saving.py             # Save handling
  ├── format_utils.py              # Formatting
  ├── keys.py                      # Key bindings
  ├── legend.py                    # Legend display
  ├── menu_selector.py             # Menu selection
  ├── selection_dialog.py          # Selection dialogs
  ├── selection_dialog_render.py   # Selection rendering
  ├── selector.py                  # Selector component
  ├── session_browser.py           # Session browser
  ├── session_detail.py            # Session detail view
  ├── status.py                    # Status display
  ├── status_containers.py         # Container status
  ├── status_systemd.py            # Systemd status
  ├── status_utils.py              # Status utilities
  ├── storage.py                   # Local storage
  ├── stream_renderer.py           # Stream renderer
  ├── text_editor.py               # Text editor
  ├── text_input_cli.py            # CLI text input
  ├── text_input_utils.py          # Text input utilities
  ├── tui.py                       # Main TUI
  ├── terminal/                    # Terminal utilities
  └── __init__.py

ami/types/                         # Type definitions
  ├── api.py                       # API types
  ├── common.py                    # Common types
  ├── config.py                    # Config types
  ├── events.py                    # Event types
  ├── results.py                   # Result types
  ├── status.py                    # Status types
  └── __init__.py

ami/tools/                         # Agent tools (deleted: replaced by opencode tools)
  ├── update_cli_versions.py       # CLI version updater
  ├── test_qwen_silence.py         # Qwen test utility
  └── clean_temp_files.py          # Temp file cleanup
```

### 3.2 Agent CLI Bootstrap (Replaced by opencode-ai)

```
scripts/
  ├── package.json                 # @anthropic-ai/claude-code, @google/gemini-cli, @qwen-code/qwen-code
  ├── package.json.backup          # Same
  └── setup/node.sh                # Node agent installer

ami/scripts/bootstrap/bootstrap_agents.sh   # Agent bootstrap script
```

**Replacement:** `ami/scripts/bootstrap/bootstrap_opencode.sh` — single-file installer that runs `npm install -g opencode-ai@latest`. No local `package.json` needed — opencode is a single npm package.

**Makefile migration:**

```
install-node-agents   → DELETED  → replace by install-opencode + update-opencode
update-node-agents    → DELETED  → replace by update-opencode
```

New targets:

```makefile
.PHONY: install-opencode
install-opencode: ## Install opencode-ai globally via npm
	@echo "📦 Installing opencode-ai..."
	@bash ami/scripts/bootstrap/bootstrap_opencode.sh

.PHONY: update-opencode
update-opencode: ## Update opencode-ai to latest
	@npm update -g opencode-ai
	@echo "✅ opencode-ai updated"
```

`install-opencode` is added to the `make install` dependency chain — placed after `install-bootstrap` so Node.js is bootstrapped, and before `install-shell` so the `ami-oc` wrapper works on first use.

### 3.3 Documentation

All files moved to `docs/archive/v2/` (see §2.1).

---

## 4. Replacement Architecture

### 4.1 opencode-ai as Single Agent CLI

The npm package `opencode-ai` (v1.15.13+) becomes the sole agent CLI.

**Installation:**
```bash
npm install -g opencode-ai
# Provides: opencode CLI binary
```

**opencode.json** (updated from `opencode.template.json`):
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "llama.cpp": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama-server (agent VM)",
      "options": {
        "baseURL": "http://llamaserver:8080/v1"
      },
      "models": {
        "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf": {
          "name": "Qwen3.6-35B-A3B (256K context)",
          "limit": {
            "context": 262144,
            "output": 65536
          }
        }
      }
    },
    "openai-compatible": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "External providers",
      "options": {
        "baseURL": "http://gateway:8080/a2a/v1"
      }
    }
  },
  "web": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 4096
  }
}
```

### 4.2 Shell Integration

**`~/.bashrc` addition:**
```bash
# AMI-Agents V3 — opencode-ai as primary agent CLI
export PATH="$HOME/.ami/bin:$PATH"
alias agent="ami-oc"
alias ami="ami-oc"
alias @="ami-oc"
alias msg="ami-oc"
```

**`ami-oc` wrapper** (`ami/scripts/bin/ami-oc`): Prints the AMI welcome banner (system paths, tool versions, extension status) fresh on each invocation as environment context, then delegates to `npx opencode`. The banner output is fed as context so the agent always sees the workspace state.

```bash
#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
AMI_ROOT="$SCRIPT_DIR"
while [[ "$AMI_ROOT" != "/" && ! -f "$AMI_ROOT/pyproject.toml" ]]; do
    AMI_ROOT="$(dirname "$AMI_ROOT")"
done
export AMI_ROOT && cd "$AMI_ROOT"
WELCOME=$("$AMI_ROOT/ami/scripts/bin/ami-welcome" 2>/dev/null || echo "AMI-AGENTS workspace")
if [[ $# -gt 0 ]]; then
    exec npx opencode run "$WELCOME\n\nTask: $*" --dir "$AMI_ROOT"
else
    printf '%b\n' "$WELCOME" && echo ""
    exec npx opencode
fi
```

Full details in `docs/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md` §14.

### 4.3 Makefile Changes

| Target | Change |
|--------|--------|
| `install-node-agents` | **Deleted** — replaced by `install-opencode` |
| `update-node-agents` | **Deleted** — replaced by `update-opencode` |
| `install-opencode` | **New** — `npm install -g opencode-ai` via `bootstrap_opencode.sh`, added to `make install` chain |
| `update-opencode` | **New** — `npm update -g opencode-ai` |
| `install` | Add `$(MAKE) install-opencode` dependency after `install-bootstrap`, before `install-shell` |
| `install-hooks` | **Unchanged** — AMI-CI hooks are agent-agnostic |
| `sync` | **Unchanged** — uv sync for Python CI tools |
| `test` | **Unchanged** — pytest for Python CI tests |
| `help` | Add opencode-ai targets |

### 4.4 Dev Shell

The `opencode` terminal UI runs inside the agent VM container (see §5). For host-side management, a thin `ami` alias wraps `opencode --headless` for batch commands.

---

## 5. Docker Virtualisation Stack

### 5.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Host Machine                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Docker Network: ami-agent-net                  │    │
│  │                                                          │    │
│  │  ┌──────────────────────┐    ┌──────────────────────┐   │    │
│  │  │  Agent Container      │    │  LLM Container       │   │    │
│  │  │  (ami-agent-vm)       │    │  (llamaserver)       │   │    │
│  │  │                       │    │                      │   │    │
│  │  │  opencode CLI/TUI     │    │  llama-server        │   │    │
│  │  │  opencode web UI      │◄───│  port 8080           │   │    │
│  │  │  127.0.0.1:4096       │    │                      │   │    │
│  │  │  A2A client           │    │  Qwen GGUF model     │   │    │
│  │  │                       │    │                      │   │    │
│  │  └──────────┬────────────┘    └──────────────────────┘   │    │
│  │             │                                              │    │
│  │  ┌──────────▼────────────┐                               │    │
│  │  │  Traefik Proxy         │                               │    │
│  │  │  (ami-traefik)        │                               │    │
│  │  │                       │                               │    │
│  │  │  HTTPS :443           │                               │    │
│  │  │  mTLS required        │                               │    │
│  │  │  ↓                    │                               │    │
│  │  │  opencode web :4096   │                               │    │
│  │  └──────────────────────┘                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Client with diagonal.crt+key → https://ami-agent.local:443     │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Dockerfile.agent

```dockerfile
FROM node:22-slim

# Install opencode-ai
RUN npm install -g opencode-ai@latest

# Create ami user
RUN useradd -m -s /bin/bash ami
USER ami
WORKDIR /home/ami

# Default opencode config
COPY opencode.docker.json /home/ami/.config/opencode/config.json

# A2A agent card directory
COPY agent-cards/ /home/ami/.config/opencode/agent-cards/

EXPOSE 4096

# Default: start opencode web UI
CMD ["opencode", "web", "--host", "127.0.0.1", "--port", "4096"]
```

### 5.3 docker-compose.yml (Agent Stack)

```yaml
services:
  llamaserver:
    image: ghcr.io/ggerganov/llama.cpp:full
    container_name: ami-llamaserver
    restart: unless-stopped
    environment:
      LLAMA_MODEL: /models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
      LLAMA_N_CTX: 262144
      LLAMA_HOST: 0.0.0.0
      LLAMA_PORT: 8080
    volumes:
      - /home/ami/AMI-AGENTS/models:/models:ro
    ports:
      - "127.0.0.1:8081:8080"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: ami-agent-vm
    restart: unless-stopped
    depends_on:
      - llamaserver
    volumes:
      - agent-data:/home/ami/.local/share/opencode
      - agent-config:/home/ami/.config/opencode
      - /home/ami/AMI-AGENTS/projects:/home/ami/projects:ro
    ports:
      - "127.0.0.1:4096:4096"

  traefik:
    image: traefik:v3.3
    container_name: ami-traefik
    restart: unless-stopped
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.internal.acme.tlschallenge=false"
    ports:
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/config:/etc/traefik:ro
      - ./traefik/certs:/certs:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.opencode.rule=PathPrefix(`/`)"
      - "traefik.http.routers.opencode.entrypoints=websecure"
      - "traefik.http.routers.opencode.tls=true"
      - "traefik.http.services.opencode.loadbalancer.server.url=http://agent:4096"
      - "traefik.http.routers.opencode.tls.options=mtls@file"

volumes:
  agent-data:
  agent-config:
```

### 5.4 Traefik mTLS Configuration

**`traefik/config/tls.yml`:**
```yaml
tls:
  options:
    mtls:
      minVersion: VersionTLS13
      clientAuth:
        clientAuthType: RequireAndVerifyClientCert
        caFiles:
          - /certs/ca.crt
  certificates:
    - certFile: /certs/server.crt
      keyFile: /certs/server.key
```

**`traefik/config/dynamic.yml`:**
```yaml
http:
  routers:
    opencode:
      rule: "Host(`ami-agent.local`)"
      entryPoints:
        - websecure
      service: opencode
      tls:
        options: mtls@file
  services:
    opencode:
      loadBalancer:
        servers:
          - url: "http://agent:4096"
```

### 5.5 Certificate Generation (The "Diagonal Part")

The diagonal part is the client certificate — known to the deployer only. Without it, the Traefik gateway returns TLS error before any HTTP response.

```bash
# Generate CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha512 -days 3650 \
  -out ca.crt -subj "/CN=AMI-Agent-CA"

# Generate server cert (signed by CA)
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr \
  -subj "/CN=ami-agent.local"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 3650 -sha512

# Generate client cert (the diagonal — one per authorized user)
openssl genrsa -out diagonal.key 4096
openssl req -new -key diagonal.key -out diagonal.csr \
  -subj "/CN=ami-admin"
openssl x509 -req -in diagonal.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out diagonal.crt -days 3650 -sha512

# Deploy
cp server.crt server.key ca.crt traefik/certs/
# Send diagonal.crt + diagonal.key to authorized client only
```

### 5.6 Integration with AMI-DATAOPS Stack

The existing AMI-DATAOPS `docker-compose.yml` remains independent. The agent stack runs as a **separate compose project** (`docker-compose -p ami-agent`), but shares the network:

```yaml
networks:
  default:
    name: ami-dataops_default
    external: true
```

This enables the agent container to access postgres, keycloak, etc. at their container hostnames.

---

## 6. Traefik HTTPS with Client Certificate Authentication

### 6.1 Requirements

| Requirement | Detail |
|-------------|--------|
| T-1 | All external access to opencode web UI MUST go through Traefik |
| T-2 | Traefik MUST terminate TLS 1.3 with server certificate |
| T-3 | Client certificate authentication MUST be required (mTLS) |
| T-4 | Only clients with a valid diagonal certificate MAY connect |
| T-5 | Traefik SHALL NOT accept plain HTTP from external networks |
| T-6 | opencode web UI SHALL bind to 127.0.0.1:4096 inside container (not exposed to external networks from the container) |
| T-7 | The diagonal certificate SHALL be distributed out-of-band (not committed to repo) |

### 6.2 Access Flow

```
Client with diagonal.crt
       │
       │ https://ami-agent.local:443
       ▼
Traefik (external port :443)
       │
       │ TLS 1.3 handshake
       │ Request client cert (CertificateRequest)
       │ Verify against ca.crt
       │
       ├─ Invalid/missing cert → TLS alert (certificate_required)
       │
       ▼ Valid cert → route to service
       │
       │ http://agent:4096 (internal Docker network)
       ▼
opencode web UI
```

---

## 7. Ansible Orchestration

### 7.1 New Playbooks

| Playbook | Purpose |
|----------|---------|
| `site.yml` | Top-level playbook — orchestrates full stack deployment |
| `opencode.yml` | Deploy/update opencode-ai globally |
| `agent-docker.yml` | Build Dockerfile.agent, manage agent compose stack |
| `traefik.yml` | Deploy Traefik configuration, manage certificates |
| `llamaserver.yml` | Existing — unchanged, manage LLM backend |

### 7.2 `site.yml`

```yaml
---
- name: AMI-Agents V3 — Full Stack Deployment
  hosts: localhost
  gather_facts: true

  vars:
    opencode_version: "latest"
    agent_domain: "ami-agent.local"
    agent_web_port: 4096
    llm_model_path: "/home/ami/AMI-AGENTS/models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"

  tasks:
    - name: Include opendeploy role
      ansible.builtin.include_role:
        name: opendeploy
      vars:
        deploy_component: opencode

    - name: Include agent-docker role
      ansible.builtin.include_role:
        name: agent-docker
      vars:
        deploy_component: docker

    - name: Include traefik role
      ansible.builtin.include_role:
        name: traefik
      vars:
        deploy_component: traefik

    - name: Include llamaserver role
      ansible.builtin.include_role:
        name: llamaserver
      vars:
        deploy_component: llamaserver
```

### 7.3 Ansible Role: `opencode`

**`ansible/roles/opencode/tasks/main.yml`:**
```yaml
---
- name: Install opencode-ai globally
  npm:
    name: opencode-ai
    state: latest
    global: true
  become: true

- name: Ensure opencode config directory exists
  file:
    path: "{{ ansible_env.HOME }}/.config/opencode"
    state: directory
    mode: "0700"

- name: Deploy opencode.json
  template:
    src: opencode.json.j2
    dest: "{{ ansible_env.HOME }}/.config/opencode/config.json"
    mode: "0600"

- name: Verify opencode installation
  command: opencode --version
  register: opencode_version_result
  changed_when: false
  failed_when: opencode_version_result.rc != 0
```

---

## 8. Bootstrapping & Installation

### 8.1 New Installation Flow

```
1. git clone AMI-AGENTS
2. sudo make pre-req          — system deps (docker, docker-compose, openssl)
3. make install               — bootstrap + certificates + compose up
```

### 8.2 `make install` Targets (Updated)

**Dependency chain for `make install`:**
```
pre-req-check → sync-package → bootstrap-gitleaks → setup-config →
install-bootstrap → install-opencode → register-extensions → install-hooks → install-shell → welcome
```

| Target | Action |
|--------|--------|
| `pre-req` | Install system deps: docker, docker-compose, openssl, curl, node/npm |
| `bootstrap-certs` | Generate CA + server + client certs (first run) |
| `compose-build` | `docker compose -f docker/docker-compose.yml build` |
| `compose-up` | `docker compose -f docker/docker-compose.yml up -d` |
| `compose-down` | `docker compose -f docker/docker-compose.yml down` |
| `install-opencode` | `bash ami/scripts/bootstrap/bootstrap_opencode.sh` — `npm install -g opencode-ai` |
| `update-opencode` | `npm update -g opencode-ai` — updates opencode to latest |
| `install-shell` | Register `ami-oc` alias + extensions in `~/.bashrc` |
| `install-hooks` | Pre-commit hooks (unchanged from V2) |
| `install` | Full: pre-req-check → sync → bootstrap → opencode → extensions → hooks → shell |
| `status` | Show stack status (compose ps + opencode --version) |
| `logs` | Tail compose logs |
| `update` | `docker compose pull` + `compose-up` |
| `client-cert` | Generate new diagonal client cert for a new user |

### 8.3 First-Run Certificate Bootstrap

```bash
# make bootstrap-certs
CERT_DIR="docker/traefik/certs"
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/ca.crt" ]; then
    echo "Generating CA and certificates..."
    openssl genrsa -out "$CERT_DIR/ca.key" 4096
    openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha512 \
      -days 3650 -out "$CERT_DIR/ca.crt" \
      -subj "/CN=AMI-Agent-CA"

    openssl genrsa -out "$CERT_DIR/server.key" 4096
    openssl req -new -key "$CERT_DIR/server.key" \
      -out /tmp/server.csr -subj "/CN=ami-agent.local"
    openssl x509 -req -in /tmp/server.csr -CA "$CERT_DIR/ca.crt" \
      -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
      -out "$CERT_DIR/server.crt" -days 3650 -sha512

    echo "Generating default admin client certificate..."
    openssl genrsa -out "$CERT_DIR/diagonal.key" 4096
    openssl req -new -key "$CERT_DIR/diagonal.key" \
      -out /tmp/diagonal.csr -subj "/CN=ami-admin"
    openssl x509 -req -in /tmp/diagonal.csr -CA "$CERT_DIR/ca.crt" \
      -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
      -out "$CERT_DIR/diagonal.crt" -days 3650 -sha512

    chmod 600 "$CERT_DIR"/*.key
    echo "Certificates generated."
    echo "Client cert: $CERT_DIR/diagonal.crt"
    echo "Client key:  $CERT_DIR/diagonal.key"
    echo "CA cert:     $CERT_DIR/ca.crt"
fi
```

---

## 9. Migration Phases

### Phase 1: Documentation & Preparation (Days 1-2)

| Action | Detail |
|--------|--------|
| 1.1 | Archive all V2 docs to `docs/archive/v2/` |
| 1.2 | Delete Python agent orchestration code (§3.1) |
| 1.3 | Delete agent CLI scripts (§3.2) |
| 1.4 | Write new `AGENTS.md` and `README.md` |
| 1.5 | **EXECUTED 2026-06-01** — Code deletions complete (Phase 1-5 of `MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md`) |

**Artifacts:** Updated docs, cleaned repo. `ami/cli_components` and `ami/types` now live in AMI-DATAOPS.

### Phase 2: Base opencode Integration (Days 3-4)

| Action | Detail |
|--------|--------|
| 2.1 | `npx opencode` available (v1.15.13 installed at `~/.local/npm-global/bin/opencode`) |
| 2.2 | Draft `opencode.docker.json` with llama.cpp + web UI config |
| 2.3 | **Replace** `install-node-agents` + `update-node-agents` with `install-opencode` + `update-opencode` in Makefile |
| 2.4 | **Create** `ami/scripts/bootstrap/bootstrap_opencode.sh` — `npm install -g opencode-ai@latest` |
| 2.5 | **Add** `$(MAKE) install-opencode` to `make install` dependency chain (after `install-bootstrap`, before `install-shell`) |
| 2.6 | **NUKE** `ami-agent` and `ami-transcripts` — replaced by single `ami-oc` wrapper (§14 of CLI-COMPONENTS doc) |
| 2.7 | **NUKE** `scripts/package.json`, `scripts/package.json.backup`, `ami/scripts/bootstrap/bootstrap_agents.sh` |
| 2.8 | **CREATE** `ami/scripts/bin/ami-oc` — prints `ami-welcome` banner fresh as agent context, delegates to `npx opencode` |
| 2.9 | Update `shell-setup`: `@` and `msg` aliases → `ami-oc` |
| 2.10 | Update `extension.manifest.yaml`: remove ami-agent/ami-transcripts, add ami-oc |
| 2.11 | **NUKE** agent test files (27 files — see §12.1) |
| 2.12 | Update `test_setup_shell_aliases.py`: replace agent aliases with `ami-oc` |
| 2.13 | Verify opencode CLI + ami-oc work in dev shell |

**The only surviving agent alias:** `ami-oc` — prints the AMI welcome banner (system paths, tool versions, extension status) fresh on each invocation as environment context, then delegates to `npx opencode`.

**Full command mapping and migration sequence:** `docs/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md` §14.

### Phase 3: Containerisation (Days 5-8)

| Action | Detail |
|--------|--------|
| 3.1 | Write `Dockerfile.agent` |
| 3.2 | Write `docker/docker-compose.yml` (agent + llamaserver + traefik) |
| 3.3 | Write `docker/traefik/config/tls.yml` and `dynamic.yml` |
| 3.4 | Write certificate bootstrap script (`ami/scripts/bootstrap/bootstrap_certs.sh`) |
| 3.5 | Build and test locally |
| 3.6 | Write Ansible playbooks for deployment |

**Artifacts:** Running agent stack in Docker with mTLS.

### Phase 4: Makefile & Bootstrap (Days 9-10)

| Action | Detail |
|--------|--------|
| 4.1 | Update `Makefile` — new targets for compose management |
| 4.2 | Update `ami/scripts/pre-req.sh` — add docker deps |
| 4.3 | Update `ami/scripts/bootstrap/` — add opencode bootstrap |
| 4.4 | Test full `make install` from clean state |

**Artifacts:** Full installation flow works end-to-end.

### Phase 5: Verification & Hardening (Days 11-12)

| Action | Detail |
|--------|--------|
| 5.1 | Verify opencode web UI accessible only via mTLS |
| 5.2 | Verify opencode web UI NOT accessible on host :4096 directly |
| 5.3 | Verify container isolation (agent cannot access host filesystem except mounted paths) |
| 5.4 | Verify A2A integration (if applicable) |
| 5.5 | Verify all pre-commit hooks still pass |
| 5.6 | Verify `ami/` Python tests still pass (CI/config code) |

**Artifacts:** Signed-off verification report.

### Phase 6: Documentation & Cleanup (Day 13)

| Action | Detail |
|--------|--------|
| 6.1 | Update `docs/README.md` with V3 architecture overview |
| 6.2 | Write ops runbook for docker stack management |
| 6.3 | Write certificate renewal procedure |
| 6.4 | Final commit with all changes |

**Artifacts:** Complete V3 documentation.

---

## 10. Verification

### 10.1 Acceptance Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `opencode` is the only agent CLI installed | `which claude` → not found; `which opencode` → found |
| AC-2 | No old agent source code in repo | `find ami -name "*claude*" -o -name "*gemini*" -o -name "*qwen*"` → empty |
| AC-3 | Old docs are archived | `ls docs/archive/v2/` → populated |
| AC-4 | Docker stack builds | `docker compose -f docker/docker-compose.yml build` → exit 0 |
| AC-5 | opencode web UI responds | `curl -sfk https://127.0.0.1:443` → TLS error (no client cert) |
| AC-6 | mTLS works with diagonal cert | `curl -sfk --cert diagonal.crt --key diagonal.key https://127.0.0.1:443` → 200 |
| AC-7 | opencode web UI NOT on :4096 from host | `curl -sf http://127.0.0.1:4096` → connection refused |
| AC-8 | All pre-commit hooks pass | `pre-commit run --all-files` → exit 0 |
| AC-9 | Python CI tests pass | `make test` → exit 0 |
| AC-10 | Ansible playbook runs | `ansible-playbook ansible/site.yml --check` → no errors |

### 10.2 Test Matrix

```
┌──────────────────────────────┬────────────┬──────────────┐
│           Test                │  Phase 2   │   Phase 5    │
├──────────────────────────────┼────────────┼──────────────┤
│ opencode CLI works           │     ✓      │      ✓       │
│ No old agent CLIs remain     │     ✓      │      ✓       │
│ Docker compose builds        │     —      │      ✓       │
│ Container starts             │     —      │      ✓       │
│ mTLS blocks without cert     │     —      │      ✓       │
│ mTLS allows with cert        │     —      │      ✓       │
│ :4096 inaccessible from host │     —      │      ✓       │
│ :443 -> :4096 routing works  │     —      │      ✓       │
│ Pre-commit hooks pass        │     ✓      │      ✓       │
│ Python CI tests pass         │     ✓      │      ✓       │
│ Ansible playbooks pass       │     —      │      ✓       │
│ Full clean install works     │     —      │      ✓       │
└──────────────────────────────┴────────────┴──────────────┘
```

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| opencode-ai npm package incompatible with LLM endpoint | Low | High | Test against llamaserver before migration; opencode supports OpenAI-compatible API |
| Docker socket exposure via Traefik | Low | Critical | Traefik uses read-only Docker socket; network isolated to `ami-agent-net` |
| Certificate expiry breaks access | Medium | High | Automated renewal playbook; monitoring; 30-day warning in `make status` |
| Loss of functionality from old agent CLIs | Medium | Medium | Audit all `ami-*` commands before deletion; map each to opencode equivalent |
| Container build fails on non-Linux | Low | Low | V3 targets Linux x86_64 only (no change from V2) |
| opencode-ai version drift | Low | Low | Pin major version in bootstrap; test upgrade in CI |
| diagonal certificate leaked | Low | Critical | `gitignore` certs; deployer rotates CA; audit `make client-cert` |

---

## 12. Appendix: File Inventory

### 12.1 Files to Delete (47 files)

```
ami/cli/__init__.py
ami/cli/base_provider.py
ami/cli/claude_cli.py
ami/cli/config.py
ami/cli/constants.py
ami/cli/editor_utils.py
ami/cli/env_utils.py
ami/cli/exceptions.py
ami/cli/exec_utils.py
ami/cli/factory.py
ami/cli/gemini_cli.py
ami/cli/interface.py
ami/cli/main.py
ami/cli/mode_handlers.py
ami/cli/process_utils.py
ami/cli/provider_type.py
ami/cli/qwen_cli.py
ami/cli/streaming.py
ami/cli/streaming_utils.py
ami/cli/stream_processor.py
ami/cli/timer_utils.py
ami/cli/transcript_search.py
ami/cli/transcript_store.py
ami/cli/validation_utils.py
ami/cli_components/__init__.py
ami/cli_components/confirmation_dialog.py
ami/cli_components/cursor_manager.py
ami/cli_components/dialogs.py
ami/cli_components/editor_display.py
ami/cli_components/editor_saving.py
ami/cli_components/format_utils.py
ami/cli_components/keys.py
ami/cli_components/legend.py
ami/cli_components/menu_selector.py
ami/cli_components/selection_dialog.py
ami/cli_components/selection_dialog_render.py
ami/cli_components/selector.py
ami/cli_components/session_browser.py
ami/cli_components/session_detail.py
ami/cli_components/status.py
ami/cli_components/status_containers.py
ami/cli_components/status_systemd.py
ami/cli_components/status_utils.py
ami/cli_components/storage.py
ami/cli_components/stream_renderer.py
ami/cli_components/text_editor.py
ami/cli_components/text_input_cli.py
ami/cli_components/text_input_utils.py
ami/cli_components/tui.py
ami/core/__init__.py
ami/core/bootloader_agent.py
ami/core/config.py
ami/core/constants.py
ami/core/conversation.py
ami/core/env.py
ami/core/factory.py
ami/core/guards.py
ami/core/interfaces.py
ami/core/logic.py
ami/core/models.py
ami/core/utils.py
ami/tools/clean_temp_files.py
ami/tools/test_qwen_silence.py
ami/tools/update_cli_versions.py
ami/types/__init__.py
ami/types/api.py
ami/types/common.py
ami/types/config.py
ami/types/events.py
ami/types/results.py
ami/types/status.py
scripts/package.json
scripts/package.json.backup
scripts/setup/node.sh
ami/scripts/bootstrap/bootstrap_agents.sh
ami/scripts/bin/ami-agent                  # nuked — replaced by ami-oc (§4.2)
ami/scripts/bin/ami_transcripts.py          # nuked — replaced by opencode session

# Agent test files (nuked — tested deleted agent code)
tests/unit/test_edge_cases_basic.py
tests/unit/test_ami_agent_edge_cases_part2.py
tests/integration/test_ami_agent_interactive_integration.py
tests/e2e/test_performance.py
tests/unit/cli/test_main.py
tests/unit/cli/test_transcript_store.py
tests/unit/cli/test_transcript_search.py
tests/unit/core/test_conversation.py
tests/unit/test_session_browser.py
tests/unit/test_transcript_search.py
tests/integration/test_bootloader_agent_integration.py
```

**Total: 82 files to delete** (Phase 1 complete — agent code dirs + cli_components/types moved to DATAOPS)

### 12.2 Files to Create (13 new files)

```
docker/Dockerfile.agent
docker/docker-compose.yml
docker/traefik/config/tls.yml
docker/traefik/config/dynamic.yml
docker/traefik/.gitkeep
ami/scripts/bootstrap/bootstrap_certs.sh
ami/scripts/bootstrap/bootstrap_opencode.sh
ami/scripts/bin/ami-oc                      # opencode wrapper with welcome context
ansible/roles/opencode/tasks/main.yml
ansible/roles/opencode/templates/opencode.json.j2
ansible/roles/agent-docker/tasks/main.yml
ansible/roles/traefik/tasks/main.yml
docs/archive/v2/.gitkeep
```

### 12.3 Files to Modify (12 files)

```
Makefile                        — New compose/cert targets
README.md                       — V3 architecture
AGENTS.md                       — V3 rules (opencode focus)
opencode.template.json          — web UI config
ami/scripts/shell/shell-setup   — opencode aliases (ami-oc)
ami/scripts/bin/extension.manifest.yaml — ami-oc replaces ami-agent/ami-transcripts
ami/scripts/pre-req.sh          — Docker deps
ami/scripts/register_extensions.py  — opencode extensions
.gitignore                      — Add diagonal cert patterns
docs/README.md                  — V3 index
opencode.json                   — Production config (deployer-specific)
tests/integration/test_setup_shell_aliases.py — verify ami-oc alias
```

---

*End of Migration Plan*
