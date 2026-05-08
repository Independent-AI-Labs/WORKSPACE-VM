<p align="center">AMI Agents</p>
<p align="center">Run Claude, Gemini, and Qwen coding agents on your own infra, behind hard safety walls.</p>

<p align="center">
  <a href="https://github.com/Independent-AI-Labs/AMI-AGENTS/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat-square" /></a>
  <a href="https://www.python.org/downloads/release/python-3110/"><img alt="Python" src="https://img.shields.io/badge/python-3.11-blue?style=flat-square" /></a>
  <a href="https://github.com/Independent-AI-Labs/AMI-AGENTS/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Independent-AI-Labs/AMI-AGENTS/ci.yml?style=flat-square&branch=main" /></a>
  <img alt="Hermetic" src="https://img.shields.io/badge/toolchain-hermetic-orange?style=flat-square" />
  <img alt="moon" src="https://img.shields.io/badge/moon-workspace-purple?style=flat-square" />
</p>

---

### Installation

```bash
git clone git@github.com:Independent-AI-Labs/AMI-AGENTS.git && cd AMI-AGENTS
sudo make pre-req       # check + apt-install: make, curl, git, openssh, openssl, openvpn, tar, gzip
make install            # bootstrap TUI: pick repos (step 1), pick components (step 2)
ami-agent               # interactive AI session (alias gets registered in your shell rc)
ami-agent "ship the polymarket fix"   # one-shot query
```

Non-interactive (CI / scripts):

```bash
make install-ci         # uses ami/config/install-defaults.yaml + workspace-clones.yaml
```

The TUI's first step picks workspace repos (mandatory: AMI-CI, AMI-DATAOPS; opt-in: PORTAL, SRP, BROWSER, STREAMS, TRADING, RUST-TRADING, ZK-PORTAL, polymarket-tracker). Step two picks components grouped by purpose: Core Dependencies, Languages & Compilers, AI Coding Assistants, Infrastructure & Orchestration, Cloud & Service CLIs, Networking, Shell Utilities, Document Processing, Browser & Device Automation, Matrix & Communication.

### Agents

AMI-AGENTS multiplexes the agent CLIs you already use. Switch with `--provider` or via the session menu.

- **claude** — Anthropic Claude Code
- **gemini** — Google Gemini CLI
- **qwen** — Alibaba Qwen Code

Every provider runs through the same gate: 4-tier command policy (`observe / modify / execute / admin` with explicit confirm for admin), fail-closed hook validation pipeline (4 validators for bash, edit, output, and prompt events), non-bypassable `git-guard` and `podman-guard` wrappers in PATH. An agent that calls `git push --force` hits the wall regardless of which model emitted it.

### Stack

The umbrella clones a federated graph of repos under `projects/` (manifest at [`ami/config/workspace-clones.yaml`](ami/config/workspace-clones.yaml)). Mandatory pair:

- [`AMI-CI`](projects/AMI-CI) — the 10-target Makefile contract every repo passes.
- [`AMI-DATAOPS`](projects/AMI-DATAOPS) — sovereign data plane: Postgres + Keycloak SSO + OpenBao secrets + Redis + Dgraph + MongoDB + Prometheus + Vaultwarden + SearXNG + OpenVPN-AS, all rootless via podman.

Opt-in siblings: [`AMI-PORTAL`](projects/AMI-PORTAL), [`AMI-SRP`](projects/AMI-SRP), [`AMI-BROWSER`](projects/AMI-BROWSER), [`AMI-STREAMS`](projects/AMI-STREAMS), [`AMI-TRADING`](projects/AMI-TRADING), [`RUST-TRADING`](projects/RUST-TRADING), [`ZK-PORTAL`](projects/ZK-PORTAL), [`polymarket-insider-tracker`](projects/polymarket-insider-tracker).

### Workspace orchestration

```bash
make -C projects/AMI-DATAOPS runtime-up PROFILES=data,secrets   # bring services up
moon run :update                                                # pull + sync the graph in dep order
moon ci --affected --base origin/main                           # CI on what changed in this PR
```

moon owns the cross-repo task graph: cacheable per-task gating with declared `inputs:`, topological `^:update` walks, tag-filtered runs (`moon run --tag rust :check`), and the `ami-agents:workspace-repos-aligned` guard that blocks merges when `.moon/workspace.yml` and `workspace-clones.yaml` drift apart.

### Extensions (PATH, not menus)

24+ extensions register on PATH via per-repo `extension.manifest.yaml` files. Highlights:

- **`ami-agent`** — the AI session entrypoint.
- **`ami-mail`** — transactional + bulk mail (himalaya/pimalaya fork; ships from AMI-STREAMS).
- **`ami-backup` / `ami-restore`** — rsync snapshots + Google Drive uploads (rclone refactor in flight); ships from AMI-DATAOPS.
- **`ami-serve`** — Cloudflare Tunnel publisher with DNS provisioning.
- **`ami-intake`** / **`ami-report`** — FastAPI P2P log receiver + TUI sender for the intake side.
- **`ami-cron`** — schedule + run jobs under systemd-user.
- **`ami-tasks`** — Markdown-on-disk task store CLI (ships from AMI-SRP).
- **`ami-kcadm`** — Keycloak admin shim.
- **`ami-bootstrap-repos`** — chicken-egg-safe workspace clone walker.

### Documentation

- [`docs/`](docs/) — architecture, migration plans, postmortems
- [`projects/AMI-CI/README.md`](projects/AMI-CI/README.md) — the contract every repo here passes
- [`docs/MOON-MIGRATION-PLAN.md`](docs/MOON-MIGRATION-PLAN.md) — workspace orchestrator design
- [`ami/config/`](ami/config/) — bootstrap component manifest, workspace clones, install defaults

### Contributing

Read [`projects/AMI-CI/README.md`](projects/AMI-CI/README.md) before opening a PR. New repos in this workspace must declare their `moon.yml`, pass `make contract-check`, and land in [`ami/config/workspace-clones.yaml`](ami/config/workspace-clones.yaml).

### FAQ

#### How is this different from running Claude Code raw?

- **Hard safety walls.** `git-guard`, `podman-guard`, fail-closed hook validators sit in PATH. An agent can't bypass them by changing prompts.
- **Provider-agnostic.** One session, one transcript, one policy across Claude, Gemini, Qwen.
- **Sovereign by default.** Your Postgres, your Keycloak, your secrets. AMI-DATAOPS brings the whole stack up rootless on your box; no daemon, no cloud control plane.
- **Workspace orchestrator.** moon walks the dep graph for you; `make update` pulls + syncs every repo in topological order.
- **Hermetic toolchain.** `.boot-linux/` holds uv, python, gcc, moon, podman, gh, ansible. No system contamination.

#### Why not just install Claude Code and OpenCode side by side?

Two install paths, two policy surfaces, two transcript stores, and the safety wrappers only work for one of them. AMI-AGENTS is the gate; the agent CLI is interchangeable.

#### Where does AMI-CI fit?

It's the contract every sibling repo passes: native git hooks generated from `.pre-commit-config.yaml`, gitleaks + sensitive-file + banned-pattern + silent-swallow + file-length + dead-code + dep-version + markdown-ref + commit-history checks, plus a 10-target Makefile contract enforced by `make contract-check`.

---

**License** [MIT](LICENSE)
