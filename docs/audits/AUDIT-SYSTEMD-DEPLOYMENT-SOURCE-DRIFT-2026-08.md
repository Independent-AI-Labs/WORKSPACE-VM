# Systemd Deployment and Source Drift Audit

**Date:** 2026-08-16  
**Scope:** System and user systemd units on `vm-ws`, their enablement state,
and their authoritative provisioning sources  
**Status:** Remediated; credential rotation pending

## Executive Summary

The host had eight project-owned user units and no project-owned system units.
All deployed units parsed successfully and no system or user unit was failed,
but the healthy runtime concealed serious provisioning drift:

- WORKSPACE-CI's current production playbook could not render its unit because
  it referenced an undefined variable and selected a Podman path that does not
  exist in the writable source tree.
- The Wiki tunnel token was stored in a world-readable unit and passed in the
  process command line.
- WORKSPACE-PORTAL was deployed from an untracked workspace-level installer
  instead of its project-owned Ansible playbook.
- Portal source referenced a missing failure-notifier unit and formed the
  notifier instance name with a duplicate `.service` suffix.
- Llamafile's deployed unit and environment file lagged their provisioning
  source, and the service had no managed-service declaration.
- The workspace status command ignored every deployed project unit because its
  prefix list only covered outdated service names.
- The tracked OpenVPN bootstrap script had been corrupted by a prior bulk edit,
  making future service installation impossible.

The runtime was not edited during discovery. Remediation is performed in
authoritative source first and deployment follows only through existing
project Make/Ansible workflows. `projects/CI` is an immutable deployed payload
and is never edited.

## Method

The audit used read-only systemd and filesystem inspection:

- `systemctl --user list-unit-files`, `list-timers`, `list-sockets`, `show`,
  `is-enabled`, and `--failed`
- system-scope `systemctl --failed` and `systemd-delta`
- `systemd-analyze --user verify` against every project-owned user unit
- deployed unit comparison with project templates and rendering playbooks
- enablement comparison with `default.target.wants` and `timers.target.wants`
- repository status and diff inspection to distinguish deployed drift from
  uncommitted source changes

Secrets discovered during inspection are intentionally omitted.

## Deployed Inventory

| Unit | State | Enablement | Authoritative source |
| --- | --- | --- | --- |
| `gateway-compose.service` | active/running | enabled | `projects/WORKSPACE-GATEWAY/res/ansible/compose.yml` |
| `llamafile-minicpm5-1b.service` | active/running | enabled | `ansible/llamafile.yml` and `ansible/roles/llamafile/` |
| `wiki-ci-tunnel.service` | active/running | enabled | `projects/WORKSPACE-CI/res/ansible/tunnel.yml` |
| `wiki-prod-compose.service` | active/running | enabled | `projects/WORKSPACE-CI/res/ansible/prod.yml` |
| `workspace-portal-dev.service` | active/running | enabled | `projects/WORKSPACE-PORTAL/res/ansible/dev.yml` |
| `workspace-portal-dev-healthcheck.service` | inactive/dead, successful oneshot | static | `projects/WORKSPACE-PORTAL/res/ansible/dev.yml` |
| `workspace-portal-dev-healthcheck.timer` | active/waiting | enabled | `projects/WORKSPACE-PORTAL/res/ansible/dev.yml` |

No project-owned socket was deployed. User linger was enabled. The transient,
disabled Wiki development unit was removed through its official stop workflow.
The Portal healthcheck repeatedly returned HTTP 200. All seven remaining unit
files passed systemd verification. The inactive Portal healthcheck oneshot was
in its expected lifecycle state.

System scope contained only distribution and Snap units. The sole local
override reported by `systemd-delta` was Ubuntu's installer-generated
`cloud-init.service`; it is not owned by this workspace.

## Findings

### Critical: WORKSPACE-CI Production Provisioning Was Not Reproducible

`projects/WORKSPACE-CI/res/ansible/prod.yml` stopped defining
`podman_bin_dir`, while
`templates/wiki-prod-compose.service.j2` still required it for `PATH`.
Rendering the current template would fail before replacing the deployed unit.

The same source change selected
`projects/WORKSPACE-CI/.boot-linux/bin/podman`. Writable CI source deliberately
does not own a boot directory, so that executable does not exist. The active
unit correctly used the protected executable in the immutable `projects/CI`
deployment.

Required correction: resolve Podman explicitly from the immutable CI
deployment, validate that executable, and define its bin directory for the
template.

### Critical: Wiki Tunnel Secret Exposure

Token-mode tunnel provisioning rendered the Cloudflare token twice into a
mode `0644` unit: once as an environment assignment and once in `ExecStart`.
This exposed the credential through the filesystem, systemd introspection,
and process arguments.

Required correction: provision a mode `0600` token file in a mode `0700`
configuration directory, use cloudflared's `--token-file`, remove the token
file on undeploy, and rotate the previously exposed token.

### High: Portal Was Deployed Through a Parallel Untracked Path

The active Portal units were installed by
`scripts/services/install-workspace-portal-service.sh` from
`scripts/services/templates/`. This duplicated and bypassed the authoritative
project Ansible implementation. The deployed result was healthy but could not
be reproduced from `projects/WORKSPACE-PORTAL`.

Required correction: move every desired behavior into the project templates,
deploy through the project's Make/Ansible target, and delete the duplicate
workspace-level installer and templates.

### High: Portal Failure Notification Was Invalid

Both Portal service templates declared
`OnFailure=ami-failure-notify@%n.service`. No
`ami-failure-notify@.service` template was deployed or provisioned. `%n`
already includes the failed unit's suffix, so the expression also requested a
unit ending in `.service.service`.

Required correction: remove the nonfunctional dependency. A notifier may be
added later only with a complete provisioned unit, test, and credential path.

### Medium: Portal Template Drift

The deployed service used the desired ten-second restart delay but source used
five seconds. The deployed parallel template omitted source's `LE_CERT_DIR`.
The authoritative cleanup script retained an error-suppressing `find | wc`
pipeline while the deployed parallel script used `find -print -quit`.

Required correction: preserve `LE_CERT_DIR`, adopt the ten-second delay, and
use the bounded native `find` predicate in authoritative source.

### Medium: Llamafile Drift and Ownership

The deployed service logged both streams to the journal while source selected
`inherit`. Its environment file retained the obsolete
`LLAMAFILE_PARALLEL_FALLBACK` variable; runtime source uses
`LLAMAFILE_PARALLEL_RESERVE`. The missing reserve variable currently resolves
to the same default value, so this drift did not change runtime behavior.

Llamafile is a workspace-level host capability, so its authoritative role is
the root `ansible/` tree rather than a duplicate under `projects/`. That
ownership must be represented in the root managed-service inventory.

### Medium: Managed-Service Inventory and Status Were Blind

`workspace/cli/status_systemd.py` only discovered outdated prefixes such as
`ami-`, `matrix-`, and `postgres`. It ignored all eight deployed project units.
Orphan reporting then narrowed discovery again to `ami-*` user services.

Several declaration files also used unsupported keys. The loader accepts only
`compose_services` and `local_services`, while CI used `services` and Portal
used `systemd_services`. Portal omitted its healthcheck service and timer from
the declaration. Root inventory declared absent obsolete units and duplicated a
Wiki compose path through the immutable deployment instead of source.

Required correction: discover all current prefixes, support explicit service
and timer declarations, report unmanaged project-prefixed user units, and
remove stale root declarations.

### Low: Wiki Development Unit Mode

`web/scripts/dev-server.sh` generated `wiki-ci-dev.service` by shell
redirection and did not set a deterministic mode. The deployed file was mode
`0664`, unlike Ansible-managed units at `0644`.

Required correction: set mode `0644` immediately after rendering.

### High: OpenVPN Bootstrap Source Was Corrupt

The tracked `workspace/scripts/bootstrap/bootstrap_openvpn_service.sh` had the
text `is-enabled workspace-openvpn.service || enabled_rc=$?` prepended to nearly
every line. The committed script could not execute and would prevent any future
OpenVPN service installation or persistence change.

Required correction: restore the clean implementation, retain explicit exit
status handling for `systemctl is-enabled`, and validate the script with
`bash -n`.

## Consistent Components

- Gateway's deployed unit matched its current template and used the intended
  immutable CI Podman executable.
- Wiki development unit content matched its template and its disabled state
  was intentional.
- Wiki tunnel content matched its source render apart from the source-level
  credential design defect.
- Portal timer scheduling matched authoritative source.
- No failed unit, restart loop, malformed unit, or unexpected project socket
  was found.

## Remediation Record

| Work item | Status |
| --- | --- |
| Repair CI Podman resolution and template variables | Complete |
| Move Wiki tunnel token out of unit and argv | Complete |
| Consolidate Portal behavior in project Ansible | Complete |
| Remove duplicate workspace-level Portal installer | Complete |
| Reconcile Llamafile service and environment render | Complete |
| Repair status discovery, state classification, and declarations | Complete |
| Restore the corrupt OpenVPN bootstrap source | Complete |
| Validate source and deploy through official workflows | Complete |
| Rotate exposed Cloudflare tunnel and API tokens | Operator action required |

## Final Verification

Remediation was deployed only through project Make/Ansible workflows. Final
verification on 2026-08-16 established:

- `wiki-prod-compose.service`, `wiki-ci-tunnel.service`, Llamafile, and Portal
  were regenerated from their authoritative sources.
- Portal's service and healthcheck timer are active, enabled, and return HTTP
  200; unauthenticated task routes correctly return HTTP 401.
- Both user and system failed-unit queries are empty.
- Every deployed project unit passes `systemd-analyze --user verify`.
- Workspace status discovers all seven current units, renders active timers as
  healthy, and renders successful inactive oneshots as stopped rather than
  failed.
- DATAOPS's approved Ansible runtime harness reports PostgreSQL, Redis, Dgraph,
  Prometheus, OpenBao, and Keycloak healthy. Direct Podman inspection is blocked
  only in the audited agent execution context by the command guard.
- Root checks pass (`1,302 passed`, `21 skipped`; `71 passed` in the focused
  status suite), Portal's full check passes, and AMI-SRP's complete Rust and
  Node checks pass.
- The restored OpenVPN bootstrap script passes `bash -n`, is executable, and is
  below the 512-line source limit.

## Acceptance Criteria

Acceptance state:

1. Complete: every authoritative template renders and referenced audited-unit
   executable paths exist.
2. Complete: no secret remains in deployed unit text or process arguments.
3. Complete: no workspace-level duplicate Portal installer or template remains.
4. Complete: deployed units match authoritative renders and pass verification.
5. Complete: expected units and timers have correct enablement and healthy state.
6. Complete: workspace status discovers current project-owned units and reports
   unmanaged current-prefix units.
7. Complete: no system or user unit is failed after deployment.
8. Pending operator action: rotate the previously exposed Cloudflare tunnel and
   API tokens.
