# Specification: Containerised Agent Isolation

**Date:** 2026-04-26
**Status:** DRAFT
**Type:** Specification
**Requirements:** [REQ-AGENT-CONTAINERS](../requirements/REQ-AGENT-CONTAINERS.md)
**Architecture:** [ARCH-AGENT-ECOSYSTEM](../ARCH-AGENT-ECOSYSTEM.md)

This specification describes **behaviour and file layout** for the
containerised-agent stack. For acceptance criteria see the REQ. For
cross-repo positioning see the ARCH doc.

---

## Implementation Status (2026-04-26)

NOT BUILT. The host-side substrate exists (`BootloaderAgent`, provider
routing, hooks, `TranscriptStore`, podman bootstrap, `status_containers`
UI). No container images, no `ami-agentd` binary, no A2A server, no
gateway. This spec sequences the work into milestones in § 14.

---

## 1. Component Layout

| Component | Repo | Language | Path |
|-----------|------|----------|------|
| `ami-agent` (BootloaderAgent CLI) | WORKSPACE-VM | Python | `ami/core/bootloader_agent.py` |
| `ami-agentd` binary | WORKSPACE-VM | Rust (Axum) | `ami-agentd/` (new Cargo crate at repo root) |
| Compiled `ami-agentd` artifact | WORKSPACE-VM | n/a | `.boot-linux/bin/ami-agentd` |
| Container image definition | WORKSPACE-VM | Dockerfile | `Dockerfile.agent` (repo root) |
| Container entrypoint | WORKSPACE-VM | bash | `res/docker/agent-entrypoint.sh` |
| A2A server (in-container) | WORKSPACE-VM | Python | `ami_agent_a2a/` (new package) |
| Manifest registration | WORKSPACE-VM | YAML | `ami/scripts/bin/extension.manifest.yaml` |
| Gateway database | runtime | SQLite | `~/.ami/agentd.db` (default) or `$DATABASE_URL` |
| Mesh socket directory | runtime | host fs | `/tmp/ami-agentd-mesh/` |
| Per-agent UDS | runtime | host fs | `$XDG_RUNTIME_DIR/ami-agentd/<name>.sock` |

`ami-agentd` is one Rust binary with two long-lived modes (`serve` for
the gateway daemon) plus several short-lived CLI subcommands. The
binary detects `AMI_CONTAINER=1` at startup; inside a container every
subcommand exits with status 2 and message
`"ami-agentd is not available inside containers"`.

---

## 2. Container Image

### 2.1 `Dockerfile.agent`

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.11.14-slim-bookworm

ARG PROVIDER=claude
ARG INSTALL_CONFIG=ami/config/install-defaults.yaml
ARG AGENT_UID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AMI_CONTAINER=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl rsync iptables gosu ca-certificates gnupg && \
    install -d /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g ${AGENT_UID} agent && \
    useradd  -u ${AGENT_UID} -g agent -m agent && \
    install -d -o agent -g agent /workspace /transcripts /cache /run/a2a

COPY --chown=agent:agent . /opt/ami-agents
WORKDIR /opt/ami-agents
COPY ${INSTALL_CONFIG} /tmp/install-config.yaml
RUN make install-ci INSTALL_DEFAULTS=/tmp/install-config.yaml && \
    make register-extensions

COPY res/docker/agent-entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

LABEL ami.type="agent"
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD test -S /run/a2a/agent.sock || exit 1

ENTRYPOINT ["/entrypoint.sh"]
```

Build invocation:

```bash
podman build -f Dockerfile.agent \
  --build-arg PROVIDER=claude \
  --build-arg AGENT_UID=$(id -u) \
  -t ami-agent:claude .
```

The `PROVIDER` build arg is read by `make install-ci` to decide which
provider CLI to install (`@anthropic-ai/claude-code`, `@google/gemini-cli`,
or qwen). One image per provider.

### 2.2 `res/docker/agent-entrypoint.sh`

```bash
#!/bin/bash
set -euo pipefail

mode="${AMI_NETWORK_MODE:-whitelist}"
sock="${AMI_AGENT_SOCK:-/run/a2a/agent.sock}"

case "$mode" in
  whitelist)
    iptables -P OUTPUT DROP
    iptables -A OUTPUT -o lo -j ACCEPT
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    for rule in ${AMI_NETWORK_WHITELIST:-}; do
      ip="${rule%:*}"
      port="${rule##*:}"
      iptables -A OUTPUT -p tcp -d "$ip" --dport "$port" -j ACCEPT
    done
    ;;
  deny-all)
    iptables -P OUTPUT DROP
    iptables -A OUTPUT -o lo -j ACCEPT
    ;;
  allow-all) : ;;
  *) echo "unknown AMI_NETWORK_MODE: $mode" >&2; exit 2 ;;
esac

# Ensure socket dir is writable by agent user even when /run is tmpfs.
install -d -o agent -g agent -m 0750 "$(dirname "$sock")"

exec gosu agent python -m ami_agent_a2a --sock "$sock"
```

`AMI_NETWORK_WHITELIST` is space-separated `host:port` entries. The
entrypoint trusts the host IP form and does no DNS resolution itself;
DNS happens via the resolver inside the container.

---

## 3. Label Schema

Every agent container carries the labels below. `ami-agentd list` reads
them via `podman ps --filter label=ami.type=agent`. There is no
external registry file.

| Label | Source | Example | Purpose |
|-------|--------|---------|---------|
| `ami.type` | Dockerfile | `agent` | Filter for agent containers |
| `ami.provider` | `create` flag | `claude`, `qwen`, `gemini` | Provider routing |
| `ami.model` | `create` flag | `claude-sonnet-4-6` | Card metadata |
| `ami.network` | `create` flag | `whitelist`, `allow-all`, `deny-all` | Echoes `AMI_NETWORK_MODE` |
| `ami.mesh` | `create` flag | `true` / absent | Mounts `/mesh/` if true |
| `ami.created` | `create` time | `2026-04-26T12:00:00Z` | Audit |
| `ami.scope.observe` | `create` flag | `allow` / `deny` | Default agent ScopeOverride |
| `ami.scope.modify` | `create` flag | `allow` / `deny` | Default agent ScopeOverride |
| `ami.scope.execute` | `create` flag | `allow` / `deny` | Default agent ScopeOverride |
| `ami.scope.admin` | `create` flag | `allow` / `deny` | Default agent ScopeOverride |
| `ami.scope.execute_allow` | `create` flag | `\bami-browser\b` | Per-command allowlist regex |

The `ami.scope.*` labels are read once by the A2A server at startup to
build the `ScopeOverride` object passed to `BootloaderAgent.run()` (see
§ 11.2).

---

## 4. Volume Schema

Three named volumes per agent. `ami-agentd create` runs
`podman volume create` before `podman run`.

| Volume | Mount point | Survives `rm` | Contents |
|--------|-------------|---------------|----------|
| `<name>-workspace` | `/workspace` | yes (without `-v`) | Source files synced from host |
| `<name>-transcripts` | `/transcripts` | yes | `TranscriptStore` JSONL session logs |
| `<name>-cache` | `/cache` | yes | `.boot-linux`, `.venv`, `node_modules` (rebuild-expensive) |

`ami-agentd destroy <name>` removes the container then prompts for
volume deletion. `--purge` skips the prompt and runs `podman rm -v`
plus `podman volume rm <name>-{workspace,transcripts,cache}`.

Each volume is labelled `ami.agent=<name>` so
`podman volume ls --filter label=ami.agent=<name>` reports its three
volumes.

---

## 5. Credential Mounts

Read-only bind mounts, decided at `create` time based on provider:

| Provider | Host path | Container path |
|----------|-----------|----------------|
| `claude` | `~/.claude` | `/home/agent/.claude:ro` |
| `qwen`   | `~/.config/qwen` | `/home/agent/.config/qwen:ro` |
| `gemini` | `~/.config/gemini` | `/home/agent/.config/gemini:ro` |

`ami-agentd create` skips mounts whose host directory does not exist
and emits a warning. The agent's CLI subprocess re-reads credentials
from disk on every invocation, so host-side rotation takes effect on
the next agent turn (no container restart).

Open question 1 in the REQ (auto-detect provider creds) is resolved
here as: always attempt the provider's canonical path, skip silently
with a warning if absent.

---

## 6. Network Isolation

The entrypoint applies one of three modes based on `AMI_NETWORK_MODE`
(set by `ami-agentd create`).

| Mode | OUTPUT chain | DNS | Use case |
|------|--------------|-----|----------|
| `whitelist` (default) | `DROP` + explicit ACCEPT for `AMI_NETWORK_WHITELIST` | container `/etc/resolv.conf` | Production agents |
| `allow-all` | no rules added | container `/etc/resolv.conf` | Debug only |
| `deny-all` | `DROP` + loopback only | n/a | Offline replay / forensic |

Default whitelist generated by `ami-agentd create`:

| Provider | Whitelisted destinations |
|----------|--------------------------|
| `claude` | `api.anthropic.com:443`, `github.com:443`, `pypi.org:443`, `registry.npmjs.org:443` |
| `qwen`   | `dashscope.aliyuncs.com:443`, `github.com:443`, `pypi.org:443`, `registry.npmjs.org:443` |
| `gemini` | `generativelanguage.googleapis.com:443`, `github.com:443`, `pypi.org:443`, `registry.npmjs.org:443` |

Override with `--whitelist host:port,host:port,...`. Adds to the list,
does not replace it. `--whitelist-replace` replaces.

---

## 7. Mesh

Agents created with `--mesh` get `/tmp/ami-agentd-mesh:/mesh` bind
mounted. The mesh dir is created with mode `0770` and the agent UID
group; only mesh agents can read each other's sockets.

Each mesh agent advertises a symlink at startup:
`/mesh/<name>.sock -> /run/a2a/agent.sock` (the symlink target is
container-internal but the source side is shared via the bind mount,
so resolve happens inside each peer).

Inter-agent A2A delegation goes peer-to-peer via these UDS paths. The
gateway is not on the mesh hop. (Resolves REQ open question 2: mesh
peers talk directly, the CLI is not an intermediary.)

---

## 8. `ami-agentd` CLI

Each subcommand below maps to one or more `podman` commands. The
mapping is exhaustive; `ami-agentd` adds no hidden state.

| Subcommand | Translates to |
|------------|---------------|
| `create <name> --provider <p> [flags]` | `podman volume create` x3, `podman build` (if image missing), `podman run -d` with labels and mounts |
| `start <name>` | `podman start <name>` |
| `stop <name>` | `podman stop <name>` |
| `restart <name>` | `podman restart <name>` |
| `destroy <name> [--purge]` | `podman rm -v <name>` (+ `volume rm` if `--purge`) |
| `list` | `podman ps -a --filter label=ami.type=agent --format <table>` |
| `status <name>` | `podman inspect <name>` + `podman stats --no-stream <name>` |
| `logs <name> [-f]` | `podman logs [-f] <name>` |
| `shell <name>` | `podman exec -it -u agent <name> /bin/bash` |
| `root-shell <name>` | `podman exec -it -u root <name> /bin/bash` |
| `sync <name> [--path P] [--direction push\|pull] [--dry-run]` | `rsync` against `podman volume inspect ...` mountpoint |
| `discover` | `podman ps --filter label=ami.type=agent` + per-agent A2A `GetAgentCard` over UDS |
| `send <name> "msg"` | A2A `SendMessage` over UDS, prints final task |
| `serve [--port 8900] [--db PATH]` | Long-running gateway, see § 9 |

Flags accepted by `create`:

```
--provider {claude|qwen|gemini}      required
--model <id>                         optional, defaults per provider
--network {whitelist|allow-all|deny-all}   default whitelist
--whitelist host:port,...            additive
--whitelist-replace host:port,...    replaces default
--mesh                               opt into /mesh mount
--memory <size>                      default 4g
--cpus <n>                           default 2
--pids-limit <n>                     default 256
--rebuild                            force podman build before run
--scope {observe,modify,execute,admin}=allow|deny   repeatable
--execute-allow <regex>              repeatable, joined with `|`
```

Argument parsing uses Clap derives. Internal command construction goes
through a `PodmanCommand` builder with one method per flag, so emitted
arguments are testable as Rust values without spawning `podman`.

---

## 9. `ami-agentd serve` (Gateway)

### 9.1 Process model

Single Tokio runtime, Axum router on `:8900`. TLS termination in front
of Axum is the operator's responsibility (reverse proxy or
`--cert/--key` flags).

### 9.2 Routes

| Method + path | Auth | Body | Response |
|---------------|------|------|----------|
| `GET /health` | none | n/a | `{"agents": N, "ok": bool}` |
| `GET /agents` | OIDC | n/a | `[{name, provider, model, status, healthy}, ...]` |
| `GET /agents/{name}/card` | OIDC | n/a | A2A AgentCard JSON |
| `POST /agents/{name}/messages:send` | OIDC | A2A `SendMessageRequest` | A2A `SendMessageResponse` |
| `POST /agents/{name}/messages:stream` | OIDC | A2A `SendStreamingMessageRequest` | SSE stream of A2A events |
| `GET /agents/{name}/tasks` | OIDC | n/a | A2A `ListTasksResponse` |
| `GET /agents/{name}/tasks/{id}` | OIDC | n/a | A2A `Task` |

For each request the gateway opens a UDS connection to
`$XDG_RUNTIME_DIR/ami-agentd/<name>.sock` and proxies bytes after
schema validation. Streaming routes proxy SSE frames one by one
through `axum::response::sse`.

### 9.3 Auth

`Authorization: Bearer <jwt>` validated against a configured set of
issuers. Issuer config is loaded at startup from `--issuers` (repeatable
flag) or `AMI_AGENTD_ISSUERS` env var (comma-separated). For each
issuer the gateway fetches `${issuer}/.well-known/openid-configuration`
once at startup, caches the JWKS, and refreshes JWKS on `kid` miss.

Failure modes:

| Condition | Response |
|-----------|----------|
| Missing or malformed `Authorization` | 401 |
| Unknown issuer | 401, log only |
| Expired or invalid signature | 401 |
| Valid token, agent not found | 404 |
| Valid token, agent exists, podman reports `unhealthy` | 503 |

### 9.4 A2A schema validation

Request bodies for `messages:send` / `messages:stream` are validated
against types generated from the A2A v0.3 OpenAPI schema (vendored
under `ami-agentd/a2a-schema/openapi.yaml`, code-gen via
`typify` build script). On validation failure the gateway returns 400
without forwarding to the agent. (Resolves REQ open question 3:
v0.3 pin, OpenAPI artefact vendored, bumped via PR.)

### 9.5 Interaction log

SQLite by default, PostgreSQL when `DATABASE_URL` is set. Schema:

```sql
CREATE TABLE interactions (
  id            TEXT PRIMARY KEY,           -- UUIDv7
  agent_name    TEXT NOT NULL,
  user_subject  TEXT NOT NULL,              -- jwt 'sub' claim
  user_issuer   TEXT NOT NULL,              -- jwt 'iss' claim
  message_kind  TEXT NOT NULL,              -- 'send' | 'stream'
  request_body  TEXT NOT NULL,              -- JSON
  response_body TEXT,                       -- JSON (final), nullable until task completes
  task_id       TEXT,                       -- A2A task id
  status        TEXT NOT NULL,              -- 'pending' | 'completed' | 'failed' | 'cancelled'
  started_at    TEXT NOT NULL,              -- ISO8601
  completed_at  TEXT,
  duration_ms   INTEGER
);
CREATE INDEX idx_interactions_agent     ON interactions(agent_name, started_at);
CREATE INDEX idx_interactions_subject   ON interactions(user_subject, started_at);
```

For streaming requests, `response_body` is the final task JSON; SSE
frames are not persisted (would explode log size). If audit needs
per-frame data, the operator runs Podman with the journald log driver
and queries `journalctl`.

### 9.6 Rate limiting

Token-bucket per `(user_subject, user_issuer)` tuple, 60 req/min,
burst 10. On exhaustion: 429 with `Retry-After` header. Buckets are in
process memory; gateway restarts reset them.

### 9.7 Health probe

Background task, every 10s, opens UDS to each agent and issues
`GetAgentCard`. Timeout 5s. Result cached as `(name -> healthy_bool)`.
`GET /health` and `GET /agents` read from this cache. Probe failure
does not restart the agent; it only flips the gateway's view.

---

## 10. A2A Server Inside Container

### 10.1 Package layout

```
ami_agent_a2a/
├── __init__.py
├── __main__.py           # entry point: argparse --sock, run uvicorn
├── executor.py           # AMIAgentExecutor (subclass of a2a AgentExecutor)
├── card.py               # build_agent_card() reads labels via /proc/.../environ + env
└── scope.py              # build_scope_override() reads AMI_SCOPE_* env vars
```

Total target: ≤200 LOC, ≤50 LOC per file.

### 10.2 Executor contract

```python
class AMIAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        instruction = extract_text(context.message)
        scope = build_scope_override()
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def stream_callback(chunk: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, chunk)

        async def pump():
            while True:
                chunk = await queue.get()
                if chunk is None:
                    return
                await event_queue.enqueue_event(
                    TaskArtifactUpdateEvent(artifact=text_artifact(chunk))
                )

        pump_task = asyncio.create_task(pump())
        try:
            run_ctx = RunContext(
                instruction=instruction,
                stream_callback=stream_callback,
                scope_overrides=scope,
            )
            result = await asyncio.to_thread(self.agent.run, run_ctx)
        finally:
            await queue.put(None)
            await pump_task
        await event_queue.enqueue_event(TaskStatusUpdateEvent(state=COMPLETED, ...))
```

`self.agent` is a single `BootloaderAgent` instance built once at
startup with the provider determined by `AMI_PROVIDER` env var.

### 10.3 Agent card

Built once at startup from container labels and env. Cached in memory.
Card fields:

| A2A card field | Source |
|----------------|--------|
| `name` | container hostname (= `--name` from `create`) |
| `description` | `ami.description` label, or `"<provider> agent"` |
| `provider.organization` | `"AMI"` |
| `version` | `AMI_AGENT_VERSION` env, set by Dockerfile build arg |
| `capabilities.streaming` | `true` |
| `defaultInputModes` / `defaultOutputModes` | `["text/plain"]` |
| `skills` | derived from provider: e.g. claude → `["chat","code","tool-use"]` |

### 10.4 ScopeOverride from labels

The container env carries `AMI_SCOPE_OBSERVE`, `AMI_SCOPE_MODIFY`,
`AMI_SCOPE_EXECUTE`, `AMI_SCOPE_ADMIN`, `AMI_SCOPE_EXECUTE_ALLOW`
(injected by `ami-agentd create` from the `ami.scope.*` labels). Defaults
when unset:

```python
ScopeOverride(
    observe="allow",
    modify="deny",
    execute="deny",
    admin="deny",
    execute_allow=[r"\bami-browser\b"],
)
```

---

## 11. Workspace Sync

`ami-agentd sync <name> [flags]` invokes:

```
rsync -av --partial --human-readable \
  --exclude='.git' --exclude='node_modules' --exclude='.venv' \
  --exclude='.boot-linux' --exclude='__pycache__' \
  <src>/ <dst>/
```

with `<src>` and `<dst>` chosen by `--direction`:

| Direction | src | dst |
|-----------|-----|-----|
| `push` (default) | `$(pwd)` | `podman volume inspect <name>-workspace --format '{{.Mountpoint}}'` |
| `pull`           | mountpoint | `$(pwd)/.agent-pull/<name>/` |

`--path P` narrows `<src>` to `$(pwd)/P` and `<dst>` to
`<mountpoint>/P` (created if absent). `--dry-run` adds `--dry-run` to
rsync.

The sync runs as the user invoking `ami-agentd`; volume mountpoints
under `~/.local/share/containers/storage/volumes` are owned by the
user under rootless podman, so no sudo needed.

---

## 12. Container Security Flags

`ami-agentd create` always passes:

```
--userns=keep-id
--cap-drop=ALL
--cap-add=NET_ADMIN          # required for iptables in entrypoint
--security-opt=no-new-privileges
--read-only
--tmpfs /tmp:rw,noexec,nosuid,size=512m
--tmpfs /run:rw,noexec,nosuid,size=64m
--memory=<from --memory>
--cpus=<from --cpus>
--pids-limit=<from --pids-limit>
--label-file=<rendered labels>
--health-on-failure=stop
```

Writable areas inside the container: `/workspace`, `/transcripts`,
`/cache`, `/tmp`, `/run`, `/home/agent`. Everything else is read-only
because of `--read-only`. The Dockerfile's `install -d -o agent` calls
in § 2.1 create the writable mount points before the read-only flag
takes effect.

---

## 13. Health Monitoring

Two layers, both active:

| Layer | Mechanism | Cadence | Surfaced |
|-------|-----------|---------|----------|
| Podman | `HEALTHCHECK` in Dockerfile, tests UDS exists | 30s | `podman inspect --format '{{.State.Health.Status}}'` |
| Gateway | A2A `GetAgentCard` over UDS, 5s timeout | 10s | cached, exposed via `GET /health` and `GET /agents` |

`ami-agentd status <name>` prints both. A divergence (podman says
healthy, gateway says unhealthy) means the UDS exists but the A2A
server is wedged; remediation is `ami-agentd restart <name>`.

---

## 14. Implementation Milestones

The REQ is large enough that an all-at-once implementation will
stall. Sequence as below; each milestone ships and is independently
useful.

### M1: Image + entrypoint (no daemon, no A2A)

Files: `Dockerfile.agent`, `res/docker/agent-entrypoint.sh`.

Acceptance: `podman build -f Dockerfile.agent -t ami-agent:claude .`
succeeds. `podman run --rm -it ami-agent:claude bash` drops into the
agent user with iptables rules applied. No A2A server, no UDS.

### M2: `ami-agentd` Rust crate (CLI subset)

Files: `ami-agentd/Cargo.toml`, `ami-agentd/src/{main,cli,podman}.rs`,
manifest entry pointing at `.boot-linux/bin/ami-agentd`.

Subcommands in this milestone: `create`, `start`, `stop`, `restart`,
`destroy`, `list`, `status`, `logs`, `shell`, `root-shell`. No `serve`,
no `send`, no `discover`. Volume + label + security flags fully
implemented.

Acceptance: `ami-agentd create demo --provider claude` produces a
running container that passes the Dockerfile HEALTHCHECK once a stub
UDS is created (`tail -f /dev/null` substitute for the A2A server).
`ami-agentd list` shows it. `ami-agentd destroy demo --purge` cleans
up.

### M3: A2A server inside container

Files: `ami_agent_a2a/{__init__,__main__,executor,card,scope}.py`,
pyproject.toml dependency `a2a-sdk = "^0.3"`.

Acceptance: container starts, UDS at `/run/a2a/agent.sock` accepts A2A
`GetAgentCard` and `SendMessage`. `ami-agentd send demo "hello"` (now
in scope) returns a response from the BootloaderAgent loop.

### M4: Mesh + sync

Subcommand additions: `discover`, `send`, `sync`. Mesh symlink
publication at A2A server startup.

Acceptance: two mesh agents can A2A-call each other peer-to-peer.
`ami-agentd sync demo` rsyncs the host workspace into the volume.

### M5: Gateway (`ami-agentd serve`)

Files: `ami-agentd/src/serve/{mod,auth,proxy,db,health}.rs`,
schema vendoring at `ami-agentd/a2a-schema/openapi.yaml`,
SQL migrations under `ami-agentd/migrations/`.

Acceptance: gateway on `:8900` serves all routes from § 9.2; OIDC
validation works against a Keycloak issuer; SQLite log persists
interactions; `/health` reports per-agent status.

### M6: Cross-repo wiring

Browser clients (AMI-TRADING chat sidebar, AMI-SRP ops center) point
at the gateway. PostgreSQL backend exercised via `DATABASE_URL`. Rate
limiter under load.

Out of scope for this spec; tracked in
`projects/AMI-TRADING/docs/requirements/REQUIREMENTS-CHAT-BACKEND.md`.

---

## 15. File Map

| File | Purpose |
|------|---------|
| `Dockerfile.agent` | Single parameterised image, one per provider |
| `res/docker/agent-entrypoint.sh` | iptables + gosu drop, exec A2A server |
| `ami-agentd/Cargo.toml` | Rust crate root |
| `ami-agentd/src/main.rs` | Clap entry, dispatch on `serve` vs CLI subcommand |
| `ami-agentd/src/cli/` | Per-subcommand modules (`create.rs`, `list.rs`, etc.) |
| `ami-agentd/src/podman.rs` | `PodmanCommand` builder, args testable in isolation |
| `ami-agentd/src/serve/` | Axum router, OIDC, A2A proxy, DB, health probe |
| `ami-agentd/a2a-schema/openapi.yaml` | Vendored A2A v0.3 schema |
| `ami-agentd/migrations/` | SQL migrations (SQLite + PG) |
| `ami_agent_a2a/__main__.py` | Python A2A server entry, parses `--sock` |
| `ami_agent_a2a/executor.py` | `AMIAgentExecutor`, bridges A2A to BootloaderAgent |
| `ami_agent_a2a/card.py` | Agent card builder |
| `ami_agent_a2a/scope.py` | Reads `AMI_SCOPE_*` env into `ScopeOverride` |
| `ami/scripts/bin/extension.manifest.yaml` | Registers `ami-agentd` (alias to `.boot-linux/bin/ami-agentd`) |
| `~/.ami/agentd.db` | Default SQLite interaction log |
| `/tmp/ami-agentd-mesh/` | Shared mesh socket dir (mode 0770) |
| `$XDG_RUNTIME_DIR/ami-agentd/<name>.sock` | Per-agent UDS, gateway target |

---

## 16. Edge Cases

| Case | Behaviour |
|------|-----------|
| `create` invoked twice with same name | Second invocation fails with `container exists`; `--rebuild` removes first |
| Image not built and `--rebuild` not passed | Implicit `podman build` triggered; logged to stderr |
| Provider creds dir missing on host | Mount skipped, warning printed, container starts without |
| Whitelist contains hostname not IP | iptables ACCEPT rule built against hostname (resolved at rule install); will match only IPs that resolve at install time |
| Container OOM-killed | Podman exits, gateway probe flips unhealthy, `ami-agentd status` reports `oom-killed` |
| UDS path exists but A2A server crashed | Podman HEALTHCHECK sees the file, reports healthy; gateway probe times out, reports unhealthy |
| Rsync into running container | Allowed; `/workspace` is a volume, not bind-mount, so rsync hits volume mountpoint directly |
| Two mesh agents with same name | `create` rejects duplicate names container-wide; mesh has no extra check |
| Gateway started with no issuers configured | All routes except `/health` return 401 |
| JWT valid, `sub` claim missing | 401 (interaction log requires non-null subject) |
| Agent removed while gateway has open SSE | Stream ends with A2A `TaskStatusUpdateEvent state=cancelled, reason="agent removed"` |
| `destroy` without `--purge`, then `create` with same name | Volumes reused, transcripts and cache survive |
| Gateway DB schema drift | Startup runs migrations; on failure, gateway exits 1 (no implicit data loss) |
| `AMI_CONTAINER=1` unset on host (operator unset it) | `ami-agentd` runs normally; the env var is the in-container marker, not a host gate |
| Inside-container invocation of `ami-agentd` | Exits 2 with `"ami-agentd is not available inside containers"` |

---

## 17. References

- REQ acceptance criteria: [REQ-AGENT-CONTAINERS](../requirements/REQ-AGENT-CONTAINERS.md)
- Cross-repo positioning: [ARCH-AGENT-ECOSYSTEM](../ARCH-AGENT-ECOSYSTEM.md)
- Gateway requirements (browser side): `projects/AMI-TRADING/docs/requirements/REQUIREMENTS-CHAT-BACKEND.md`
- Agent profile (scope defaults rationale): `projects/AMI-TRADING/docs/requirements/REQUIREMENTS-CHAT-AGENT-PROFILE.md`
- Task engine (operational tasks, not agent execution): `projects/AMI-SRP/docs/requirements/REQUIREMENTS-TASK-ENGINE.md`
- A2A protocol: <https://github.com/google/A2A>, v0.3 OpenAPI vendored under `ami-agentd/a2a-schema/`
