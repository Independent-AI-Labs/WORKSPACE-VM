# Workspace Notification Engine - Enterprise Requirements Specification

**Document ID:** WS-REQ-NOTIFICATIONS-v0.4
**Status:** Draft - Operator decisions recorded (§9); ready for implementation
**Date:** 2026-09-13
**Classification:** Internal - Enterprise
**Specification:** [SPEC-NOTIFICATIONS](../specifications/SPEC-NOTIFICATIONS.md)
**Authors:** Workspace Engineering
**References:**
- [SPEC-NOTIFICATIONS](../specifications/SPEC-NOTIFICATIONS.md) (Technical Specification)
- [AUDIT-SYSTEMD-DEPLOYMENT-SOURCE-DRIFT-2026-08](../audits/AUDIT-SYSTEMD-DEPLOYMENT-SOURCE-DRIFT-2026-08.md) (prior OnFailure defect ruling)
- [scripts/services/ami_failure_notify.sh](../../scripts/services/ami_failure_notify.sh) (existing notifier adapter)
- [scripts/services/ami_gitleaks_sweep.sh](../../scripts/services/ami_gitleaks_sweep.sh) (migrated onto this engine in v1)
- [scripts/setup/hang-evidence-sampler.sh](../../scripts/setup/hang-evidence-sampler.sh) (forensic sampler; adjacent but distinct)
- [WORKSPACE-STREAMS docs/AMI-MAIL.md](../../projects/WORKSPACE-STREAMS/docs/AMI-MAIL.md) (mail channel authority - `ami-mail` operator guide)
- [WORKSPACE-STREAMS docs/SPEC-MAIL.md](../../projects/WORKSPACE-STREAMS/docs/SPEC-MAIL.md) (mail channel architecture; §2: "managed build, not a bootstrap")
- [WORKSPACE-STREAMS docs/MONITORING.md](../../projects/WORKSPACE-STREAMS/docs/MONITORING.md) (server-side Alertmanager precedent; alert-rule threshold catalog)
- [AGENTS.md](../../AGENTS.md) (Universal Agent Rules)

---

## 1. Scope

This document specifies functional and non-functional requirements for a
**notification engine** for the workstation: one shared mechanism that turns
operational events (unit failures, restart loops, resource exhaustion) into
operator-visible alerts over two remote channels with priorities, escalation
fast-tracking, deduplication, and secrets served from OpenBao.

The engine unifies the send path that `ami_failure_notify.sh` and
`ami_gitleaks_sweep.sh` currently duplicate, closes the
`ami-failure-notify@.service` deployment gap identified by the 2026-08 audit,
and adds restart-loop plus resource-threshold alerting motivated by the
2026-09 hang incidents.

**In scope (v1):**

- REQ/SPEC documentation (this pair)
- One shared notifier core script (`ami_notify_send.sh`): priorities,
  escalation fast-track, per-alert-key cooldown, channel fan-out
- Two channels: **email** (himalaya over Gmail SMTP) and **GitHub issue**
  (`gh issue create` with per-invocation token) - fan-out by priority
- **All credentials from OpenBao KV** (gateway pod, `127.0.0.1:8201`);
  nothing secret at rest anywhere else, nothing secret in any repo
- `ami-failure-notify@.service` systemd user template unit wired via
  `OnFailure=` **drop-in files** for workspace-managed user units
- Timer-driven health checker (`ami-health-check.*`): restart-loop detection
  (`NRestarts`), PSI, memory, disk, D-state thresholds, priority-mapped
- himalaya (`ami-mail`) provisioning **delegated to WORKSPACE-STREAMS**
  (`make -C projects/WORKSPACE-STREAMS build-himalaya` - the managed build
  per SPEC-MAIL §2); this engine adds no binary bootstrap of its own
- Operator credential runbook (Gmail app password + GitHub token written to
  OpenBao KV once; secret never enters any repository)
- `make install-notifications` / `notifications-status` / dry-run self-test
- `ami_gitleaks_sweep.sh` migrated onto the shared core; cron replaced by a
  systemd timer
- Unit tests wired into the standard pytest suite (`make check`) and the
  workspace hook/gate chain, like every other project

**Out of scope (v1):**

- System-scope (root) unit notifications - operator handoff, later phase
- Desktop `notify-send` - the primary failure class (i915 display-pipe freeze)
  kills the compositor, so local popups fail exactly when needed
- Matrix (infrastructure retired per 2026-08 audit), webhooks, chat platforms
- A monitoring daemon or metrics stack (monit / netdata / Prometheus +
  Alertmanager) - systemd is already the supervisor; shell-first per AGENTS.md
  Rule 5
- Alerting on the forensic sampler's log history (sampler stays post-mortem;
  the health checker probes live `/proc`, `df`, `systemctl`)
- Adaptive baselines, anomaly detection, or per-probe hysteresis machinery -
  static calibrated thresholds with environment overrides
- The STREAMS Prometheus/Alertmanager stack as a delivery path - it remains
  the server-side observability layer ([MONITORING.md](../../projects/WORKSPACE-STREAMS/docs/MONITORING.md))
  and is not deployed on this workstation

### 1.1 Ownership Split

Single-owner-per-artifact; no duplicate boundaries (AGENTS.md Rule 7).

| Layer | Owner | Artifacts |
|-------|-------|-----------|
| Event capture (systemd OnFailure template, drop-ins, timers, canary) | **WORKSPACE-VM** (this repo) | `scripts/services/ami-failure-notify@.service`, `ami-health-check.*`, `ami-gitleaks-sweep.*` |
| Engine core (priority, cooldown, escalation, fan-out, state) | **WORKSPACE-VM** | `ami_notify_send.sh`, `/mnt/ws-fast/notify/state/` |
| Probes of this machine (NRestarts, PSI, mem, disk, D-state) + managed-unit list | **WORKSPACE-VM** | `ami_health_check.sh` (machine topology lives here, not in a comms repo) |
| Email channel: binary build, config provisioning, upstream features | **WORKSPACE-STREAMS** | `himalaya/` fork, `make build-himalaya`, `ansible/roles/ami_mail/`, `config/himalaya/config.sample.toml` |
| Server-side alerting stack (Prometheus rules, Alertmanager routing) | **WORKSPACE-STREAMS** | `alertmanager/ami-alerts.rules` (threshold catalog precedent) |
| Secrets storage (KV v2 `secret/workspace/notify`) | **WORKSPACE-GATEWAY** | `gw-prod-pod` OpenBao (`127.0.0.1:8201`), fixed-ID service token |
| GitHub channel (`gh` binary) | **WORKSPACE-VM** boot dir | token from OpenBao per-invocation |

Cross-repo documentation follows the established pattern (REQ-VM-HYPERVISOR
references WORKSPACE-GUARD's REQ-SANDBOX): this REQ/SPEC pair is the engine
authority; STREAMS' AMI-MAIL/SPEC-MAIL are the channel authority. STREAMS'
AMI-MAIL.md records this engine as a documented consumer.

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Notification engine** | Shared send path: priority, dedup, fan-out, deliver |
| **Alert key** | Stable identifier for one alert source (e.g. `restart:compliance-analytics`) |
| **Priority** | `critical` \| `urgent` \| `normal`; drives cooldown, fan-out, subject prefix |
| **Escalation fast-track** | A higher-priority delivery for a key bypasses the remaining cooldown of a lower-priority prior delivery |
| **Cooldown** | Minimum seconds between two deliveries for the same alert key at the same priority |
| **OnFailure template** | `ami-failure-notify@.service` instantiated per failed unit |
| **Drop-in** | `~/.config/systemd/user/<unit>.d/10-workspace-notify.conf` adding `OnFailure=` without editing unit sources across repos |
| **Restart loop** | Service repeatedly failing while `Restart=` keeps it out of `failed` state; invisible to `OnFailure=` |
| **Channel** | Delivery transport; v1: himalaya email + GitHub issue |
| **Dry run** | Engine mode that composes and logs but never invokes any channel |
| **OpenBao** | Local secrets server (gateway prod pod); KV v2 at `secret/`, host API `127.0.0.1:8201` |

---

## 3. Problem Statement

Three concrete operational failures motivate the engine:

1. **Broken OnFailure wiring.** Portal templates declared
   `OnFailure=ami-failure-notify@%n.service`; no template unit was ever
   deployed, and `%n` (which already includes the `.service` suffix) produced
   a `…service.service` unit id. `zk-portal-dev.service` carries the same
   dangling reference today.
2. **Restart loops are invisible.** On 2026-09-13 `compliance-analytics.service`
   exited with failure 125 consecutive times (SurrealDB unreachable) while
   remaining in `activating/auto-restart` - systemd never enters `failed`, so
   no `OnFailure=` path can fire. Nobody noticed for ~25 minutes.
3. **No channel exists.** Both notifier scripts target himalaya, but the
   binary is absent from both boot directories and PATH, and no credential
   path exists. The audit requires any notifier to ship with a complete
   provisioned unit, test, and credential path.

```
unit failure ──────► OnFailure= template ─┐
restart loop ──────► NRestarts probe ─────┤──► ami_notify_send ─► priority + cooldown ─► fan-out ─┬─► email
resource limits ───► threshold probe ─────┘   (state on /mnt/ws-fast)                            └─► gh issue
                                                                        secrets ◄─ OpenBao KV (send-time fetch)
```

---

## 4. Functional Requirements

### FR-1: Shared notifier core

**FR-1.1 (REQ-NOT-001)** A single script `scripts/services/ami_notify_send.sh`
SHALL accept `--key <alert-key> --subject <s> --priority <critical|urgent|normal>`
(default `normal`) plus `--body <text>` / `--body-file <path>` and own
priority handling, cooldown evaluation, channel fan-out, and delivery.

**FR-1.2 (REQ-NOT-002)** Cooldown state SHALL persist per alert key under
`/mnt/ws-fast/notify/state/` as `<epoch> <priority>` records. Same-priority
re-delivery inside the cooldown window SHALL be skipped and logged, not
queued. **Escalation fast-track:** a delivery whose priority rank exceeds
the stored rank SHALL bypass the remaining cooldown and send immediately
(REQ-NOT-011 mapping: critical > urgent > normal).

**FR-1.3 (REQ-NOT-003)** `WORKSPACE_NOTIFY_DRY_RUN=1` SHALL compose and log
the full message and resolved priority without invoking any channel. Tests
and self-tests use this mode. The refactored adapter (FR-1.4) switches to
this variable name exclusively - the previous
`WORKSPACE_FAILURE_NOTIFY_DRY_RUN` name is removed, not aliased.

**FR-1.4 (REQ-NOT-004)** `ami_failure_notify.sh` SHALL be refactored into a
thin adapter: systemd-state/journal capture stays, send logic delegates to
the core with priority `urgent`. Exit-code contract (0/2/3/4) preserved.

**FR-1.5 (REQ-NOT-005)** Every channel invocation SHALL hard-timeout (60s
send; 5s secret fetch) and surface transport failure as a distinct non-zero
exit so notifier failure is visible in `journalctl -u ami-failure-notify@*`.

### FR-2: Priorities and fan-out

**FR-2.1 (REQ-NOT-006)** Priorities SHALL map to cooldowns: `normal` 1800s,
`urgent` 300s, `critical` 60s (environment-overridable per level). Subject
lines SHALL carry the prefix `[CRITICAL]` / `[URGENT]` / `[NOTICE]`
respectively.

**FR-2.2 (REQ-NOT-007)** Channel fan-out SHALL be priority-driven:
`critical` and `urgent` deliver to **both** email and GitHub issue;
`normal` delivers email only. Every configured channel is attempted;
**failure of any channel fails the send** (exit `4`, notifier unit enters
`failed`, journal names the failing channel). There is no partial-success
outcome.

**FR-2.3 (REQ-NOT-008)** GitHub issue creation SHALL be idempotent per
incident: before creating, the channel searches the target repository for an
open issue whose title contains the alert key; an existing issue receives a
comment (new occurrence summary) instead of a duplicate. Issue titles SHALL
embed the alert key as the stable search handle.

**FR-2.4 (REQ-NOT-009)** The escalation path SHALL be observable: a
fast-tracked send logs `escalation <old>→<new>` so the journal shows why
cooldown was bypassed.

### FR-3: Unit-failure path (OnFailure)

**FR-3.1 (REQ-NOT-010)** An `ami-failure-notify@.service` user template unit
SHALL be deployed by `make install-notifications` to
`~/.config/systemd/user/`, invoking the adapter with the failed unit id.

**FR-3.2 (REQ-NOT-011)** Wiring SHALL use drop-in files
(`<unit>.d/10-workspace-notify.conf`) containing
`OnFailure=ami-failure-notify@%N.service` - `%N` (name without suffix)
avoids the audit's `…service.service` defect. Unit sources in other repos are
not edited.

**FR-3.3 (REQ-NOT-012)** The managed-unit list SHALL cover the
workspace-operated user services (§7 AC-3 enumerates them); adding a unit
SHALL require only a one-line list change plus re-run of the installer.

**FR-3.4 (REQ-NOT-013)** The notifier unit itself SHALL NOT carry
`OnFailure=` (notification loops are a defect, not a feature).

### FR-4: Restart-loop detection

**FR-4.1 (REQ-NOT-014)** The health checker SHALL read `NRestarts` (and
`ActiveState`) via `systemctl --user show` for each managed unit and emit an
`urgent` alert keyed `restart:<unit>` when NRestarts exceeds the threshold.

**FR-4.2 (REQ-NOT-015)** The checker SHALL report NRestarts in its output
(monotonic counter) so a human can distinguish "looping since boot" from
"newly looping"; the cooldown prevents repeat mail either way.

### FR-5: Resource thresholds

**FR-5.1 (REQ-NOT-016)** The health checker SHALL probe live state (not the
forensic sampler logs): PSI `some avg10` for io/cpu/memory from
`/proc/pressure/*`, `MemAvailable` from `/proc/meminfo`, D-state process
count, and filesystem usage (`df -P`) for `/` and `/mnt/ws-fast`.

**FR-5.2 (REQ-NOT-017)** Each probe SHALL map a measured value to
`critical` / `urgent` / `none` via two static thresholds (REQ-NOT-018),
environment-overridable, with defaults **calibrated to observed machine
baselines** (2026-09-13 idle: PSI ≈ 0.00 all domains, MemAvailable ≈ 87 GiB
of 128 GiB, `/` 56%, fast store 22%; the 2026-09 hang class pinned PSI io
avg10 near 100 - see SPEC §6 table) and **aligned with the STREAMS
Alertmanager precedent** (`alertmanager/ami-alerts.rules`: disk 85%/95%,
memory 90%, CPU 90%) so workstation and server alerting speak the same
numbers.

**FR-5.3 (REQ-NOT-018)** A probe whose source is absent (e.g. no PSI in
kernel) SHALL log and skip - an unmonitorable source MUST NOT abort the
remaining probes (rc-capture pattern; the skip is logged loudly).

### FR-6: Secrets - OpenBao always

**FR-6.1 (REQ-NOT-019)** ALL engine credentials (Gmail app password, GitHub
token) SHALL be stored only in the gateway OpenBao KV store
(`secret/workspace/notify`) and fetched **at send time**. No secret material
SHALL exist in any repository, unit file, config file, or test fixture.

**FR-6.2 (REQ-NOT-020)** The engine SHALL authenticate to OpenBao using the
gateway-established fixed-ID service token pattern (`OPENBAO_TOKEN` from
`projects/WORKSPACE-GATEWAY/.env`), read-only for its KV path, with
environment overrides for address and token location. The engine SHALL NOT
create, rotate, or log tokens.

**FR-6.3 (REQ-NOT-021)** himalaya's configuration SHALL reference the secret
via `passwd.cmd` (command substitution at send time); the config file itself
contains no secret material and is installer-deployed from a tracked
template.

**FR-6.4 (REQ-NOT-022)** Secret fetch SHALL be bounded (5s) with one retry;
if OpenBao is unreachable (e.g. gateway pod down, early-boot OnFailure), the
notifier SHALL fail with exit `3` naming the remediation (`systemctl --user
status gw-prod-pod.service`) - never a quiet no-send.

### FR-7: Channel and credential provisioning

**FR-7.1 (REQ-NOT-023)** himalaya provisioning SHALL be delegated to
WORKSPACE-STREAMS, the mail-channel owner: `make install-himalaya` in this
repo is a thin delegation to `make -C projects/WORKSPACE-STREAMS
build-himalaya`, which compiles the vendored fork and installs
`.boot-linux/bin/himalaya` + the `ami-mail` symlink (SPEC-MAIL §2: "a
managed build, not a bootstrap; all build logic lives in
WORKSPACE-STREAMS"). This engine SHALL NOT carry its own download, pin
manifest, or bootstrap script for himalaya. The engine SHALL resolve the
binary via the house boot-dir seam - no PATH guessing.

**FR-7.2 (REQ-NOT-024)** The `gh` channel SHALL use the bootstrapped `gh`
binary with `GH_TOKEN` resolved per-invocation from OpenBao; no interactive
`gh auth login` state is required or created.

**FR-7.3 (REQ-NOT-025)** SPEC §7 SHALL provide an operator-only runbook:
create the Gmail app password, create the GitHub fine-grained token, write
both to OpenBao KV once, verify round-trip on both channels. Sign-off is an
acceptance criterion.

**FR-7.4 (REQ-NOT-026)** Missing binary, secret, or credential SHALL produce
an explicit error naming the fix command (`make install-himalaya`, runbook
path, pod status command) - never a quiet no-send.

### FR-8: Deployment, status, tests, CI

**FR-8.1 (REQ-NOT-027)** `make install-notifications` SHALL deploy template
unit, health-check service + timer, gitleaks sweep timer, drop-ins for the
managed list, daemon-reload, and enable timers - mirroring the
`install-diagnostics` pattern.

**FR-8.2 (REQ-NOT-028)** `make notifications-status` SHALL show timer states,
last checker output, notifier journal tail, and cooldown-state listing.

**FR-8.3 (REQ-NOT-029)** A self-test SHALL exist (`make
test-notifications`): start a canary unit whose `ExecStart` fails, then
assert the notifier ran in dry-run mode with the canary's unit id - proving
template, drop-in, and adapter wiring without sending mail or touching
OpenBao. In environments without a systemd user session it SHALL skip with
an explicit reason (house NFR precedent: skip honestly, never false-pass).

**FR-8.4 (REQ-NOT-030)** Unit tests for cooldown, escalation, priority
mapping, threshold math, and issue-dedup logic SHALL live in the standard
pytest suite and run under `make check` / the workspace commit gates,
identical to every other component in this repository.

**FR-8.5 (REQ-NOT-031)** `ami_gitleaks_sweep.sh` SHALL migrate onto the
shared core (same key/priority/cooldown/fan-out machinery; findings =
`urgent`, sweep failure = `normal` informational) and its weekly cron entry
SHALL be replaced by `ami-gitleaks-sweep.timer` (deployed by
`install-notifications`, `Persistent=true`).

---

## 5. Non-Functional Requirements

**NFR-1** Shell-first: bash + coreutils + curl/jq + systemd only; no new
runtime dependencies beyond the himalaya binary; no daemon besides systemd
units (AGENTS.md Rule 5).

**NFR-2** All scripts `#!/bin/bash`, `set -euo pipefail`, rc-capture
pattern (`_rc=0; cmd || _rc=$?`); no banned words; source files under 512
lines.

**NFR-3** User-scope only (uid 1000). No root escalation; system-scope
notification is a later operator phase.

**NFR-4** Boot-survivable: units enabled via systemd; state on
`/mnt/ws-fast`; `/tmp` is never used for state (tmpfs wipe).

**NFR-5** Mail-volume safety: cooldown bounded per key and priority; a
permanently violating threshold sends at most once per cooldown window at
its mapped priority; escalation is rank-gated, not volume-gated.

**NFR-6** No `OnFailure` recursion (FR-3.4); the notifier must not be able
to notify about itself.

**NFR-7** Explicit failures everywhere: every error path names the
remediation (install target, runbook, pod status, or journal command). No
swallowed exit codes.

**NFR-8** Bounded journal output per invocation (checker summarizes; full
probe detail goes into the mail body, not the journal).

**NFR-9** No secret material in any repository, unit file, template, or
test fixture - including the OpenBao token itself (read from the gateway
`.env` at runtime, path only referenced).

---

## 6. Managed Unit List (v1 baseline)

| Unit | Failure path | Restart-loop probe |
|------|--------------|--------------------|
| `zk-portal-dev.service` | drop-in | yes |
| `workspace-portal-dev.service` | drop-in | yes |
| `gateway-compose.service` | drop-in | yes |
| `wiki-prod-compose.service` | drop-in | yes |
| `wiki-ci-tunnel.service` | drop-in | yes |
| `compliance-analytics.service` | drop-in | yes |
| `llamafile-minicpm5-1b.service` | drop-in | yes |
| `hang-evidence-sampler.service` | drop-in | yes |
| `gw-prod-pod.service` | drop-in | no (oneshot) |
| `compliance-slice-pod.service` | drop-in | no (oneshot) |
| `zk-portal-pod.service` | drop-in | no (oneshot) |

Oneshot pod units use `RemainAfterExit`; their `ExecStart` failure still
transitions to `failed` and fires `OnFailure=`.

---

## 7. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | REQ/SPEC pair committed and cross-linked |
| AC-2 | Core unit tests pass under `make check`: cooldown, escalation bypass, priority→cooldown/fan-out mapping, threshold math, issue-dedup search invocation |
| AC-3 | Drop-ins installed for §6 list; `systemctl --user cat <unit>` shows `OnFailure=ami-failure-notify@%N.service` |
| AC-4 | `make test-notifications` canary proves template + drop-in + adapter in dry-run; skips honestly without a user session |
| AC-5 | Same-priority send inside cooldown skipped+logged; escalated priority bypasses and logs `escalation old→new` |
| AC-6 | `make install-himalaya` delegates to the STREAMS managed build and the binary lands in the boot dir |
| AC-7 | Operator runbook executed: both OpenBao KV entries written; email round-trip AND gh issue round-trip signed off by operator |
| AC-8 | `grep`-clean secret audit: no app password, GH token, or OpenBao token in any repo file or fixture |
| AC-9 | `make check` green; shell-guard + banned-words gates clean |
| AC-10 | `ami_failure_notify.sh` delegates to core; exit-code contract unchanged |
| AC-11 | Gitleaks sweep sends through the core (dry-run asserted in tests); weekly timer active, cron entry retired |

Execution status tracked in §11.

---

## 8. Traceability

| Requirement | Spec section | Primary artifact |
|-------------|--------------|------------------|
| FR-1 | SPEC §3 Core | `scripts/services/ami_notify_send.sh` |
| FR-2 | SPEC §3.2-3.4 | same |
| FR-3 | SPEC §4 OnFailure path | `scripts/services/ami-failure-notify@.service`, drop-ins |
| FR-4 | SPEC §5 Checker | `scripts/services/ami_health_check.sh` |
| FR-5 | SPEC §5-6 Checker | same |
| FR-6 | SPEC §7 Secrets | `scripts/services/ami_notify_secret.sh` |
| FR-7 | SPEC §6-7 Channel build + secrets | STREAMS `build-himalaya` delegation, runbook |
| FR-8 | SPEC §9-10 Deploy/test/CI | Makefile targets, tests, canary |

---

## 9. Operator Decisions (recorded 2026-09-13)

1. **Channels: ALL** - email (himalaya/Gmail) + GitHub issue, fan-out by
   priority (FR-2.2). Desktop notify stays rejected (compositor dies in the
   primary failure class).
2. **Credentials: OpenBao ALWAYS** - KV `secret/workspace/notify`, send-time
   fetch, gateway service-token pattern (FR-6).
3. **Thresholds: smart, not clever** - two static thresholds per probe
   (urgent/critical), calibrated to observed baselines, environment
   overridable; no adaptive logic (FR-5.2, SPEC §6).
4. **Cooldown + fast-track** - priority-tiered cooldowns with escalation
   bypass (FR-1.2, FR-2.1).
5. **Cadence: prod-appropriate** - 2-minute health-check timer (sub-second
   probes; matches the portal healthcheck precedent; halves restart-loop
   detection latency vs 5 min).
6. **gitleaks + CI: proper integration** - migration in v1 scope, cron →
   timer, tests inside `make check` and the commit gates like every other
   project (FR-8).
7. **Placement: engine stays in WORKSPACE-VM; responsibilities split per
   §1.1** - docs remain here (the engine is machine-topology-bound); the
   mail channel defers to WORKSPACE-STREAMS' managed build; STREAMS docs
   record this engine as a consumer.

Remaining adjustable knobs (defaults in SPEC, env-overridable, no further
decision required): exact threshold numbers, cooldown values, gh target repo
(default `Independent-AI-Labs/WORKSPACE-VM`).

---

## 10. Threshold Calibration Rationale

Observed 2026-09-13 (sampler live, idle): PSI all domains ≈ 0.00 avg10;
load ≈ 2.4; MemAvailable ≈ 87 GiB of 128 GiB; `/` 56%; fast store 22%.
Observed 2026-09 hang class: PSI io avg10 pinned near 100 for minutes,
D-state count in the hundreds, compositor frozen.

Static defaults therefore sit far above healthy noise and well below
incident reality (SPEC §6 carries the exact table); both urgent and critical
levels are defined per probe so a worsening machine escalates before it
dies.

---

## 11. Implementation Status

Status as of 2026-09-13: **not implemented** - documents drafted, operator
decisions recorded in §9; implementation may begin per SPEC §12 order.
