<p align="center">AMI Agents</p>
<p align="center">Run Claude, Gemini, and Qwen coding agents on your own infra — behind hard safety walls.</p>

<p align="center">
  <a href="https://github.com/Independent-AI-Labs/AMI-AGENTS/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat-square" /></a>
  <a href="https://www.python.org/downloads/release/python-3110/"><img alt="Python" src="https://img.shields.io/badge/python-3.11-blue?style=flat-square" /></a>
  <a href="https://github.com/Independent-AI-Labs/AMI-AGENTS/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Independent-AI-Labs/AMI-AGENTS/ci.yml?style=flat-square&branch=main" /></a>
</p>

---

### Installation

```bash
git clone git@github.com:Independent-AI-Labs/AMI-AGENTS.git && cd AMI-AGENTS
sudo make pre-req       # system deps: git, openssh, openssl, openvpn, browser libs
make install            # bootstrap TUI: pick repos, pick components
@                       # interactive session
@ "ship the polymarket fix"   # one-shot query
```

Non-interactive (CI / scripts):

```bash
make install-ci         # uses ami/config/install-defaults.yaml
```

### Agents

AMI-AGENTS multiplexes the agent CLIs you already use. Switch with `@<provider>` or via the session menu.

- **claude** — Anthropic Claude Code
- **gemini** — Google Gemini CLI
- **qwen** — Alibaba Qwen Code

Every provider runs through the same gate: tiered command policy, fail-closed hook validation, non-bypassable `git-guard` and `podman-guard` wrappers in PATH. An agent that calls `git push --force` hits the wall regardless of which model emitted it.

### Stack

The umbrella clones a federated graph of repos under `projects/`. Mandatory pair: [`AMI-CI`](projects/AMI-CI) (the contract every repo passes), [`AMI-DATAOPS`](projects/AMI-DATAOPS) (Postgres / Keycloak SSO / OpenBao secrets / Redis / MinIO).

Opt-in via the install TUI: `AMI-PORTAL`, `AMI-SRP`, `AMI-BROWSER`, `AMI-STREAMS`, `AMI-TRADING`, `RUST-TRADING`, `ZK-PORTAL`, `polymarket-insider-tracker`.

```bash
make -C projects/AMI-DATAOPS runtime-up PROFILES=data,secrets   # bring services up
moon run :update                                                # pull + sync the graph
moon ci --affected --base origin/main                           # run CI on what changed
```

### Documentation

- [`docs/`](docs/) — architecture, migration plans, postmortems
- [`projects/AMI-CI/README.md`](projects/AMI-CI/README.md) — the 10-target Makefile contract every repo here passes
- [`projects/docs/MOON-MIGRATION-PLAN.md`](projects/docs/MOON-MIGRATION-PLAN.md) — workspace orchestrator design

### Contributing

Read [`projects/AMI-CI/README.md`](projects/AMI-CI/README.md) before opening a PR. New repos in this workspace must declare their `moon.yml`, pass `make contract-check`, and land in `ami/config/workspace-clones.yaml`.

### FAQ

#### How is this different from running Claude Code raw?

- **Hard safety walls.** `git-guard`, `podman-guard`, fail-closed hook validators in PATH — an agent can't bypass them by changing prompts.
- **Provider-agnostic.** One session, one transcript, one policy across Claude, Gemini, Qwen.
- **Sovereign by default.** Your Postgres, your Keycloak, your secrets — `AMI-DATAOPS` brings the whole stack up on your box.
- **Workspace orchestrator.** moon walks the dep graph for you; `make update` pulls + syncs every repo in topological order.
- **Hermetic toolchain.** `.boot-linux/` holds uv, python, gcc, moon, podman, gh — no system contamination.

#### Why not just install Claude Code and OpenCode side by side?

Because then you have two install paths, two policy surfaces, two transcript stores, and the safety wrappers only work for one of them. AMI-AGENTS is the gate; the agent CLI is interchangeable.

---

**License** [MIT](LICENSE)
