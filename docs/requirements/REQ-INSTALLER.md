# REQ-INSTALLER: Bootstrap and Host Configuration Installer

**Date:** 2026-11-02
**Status:** Active
**Type:** Requirements
**Specification:** [SPEC-INSTALLER](../specifications/SPEC-INSTALLER.md)

> Contract for the workspace installers: the non-root component TUI
> (`make install`), its non-interactive form (`make install-ci`), and the
> privileged host configuration stage (`sudo make init`). This document owns
> lifecycle boundaries, install ordering, auxiliary feature selection, and the
> storage configuration step.

---

**Cross-references:**
- [SPEC-INSTALLER](../specifications/SPEC-INSTALLER.md): companion specification
- [`workspace/config/bootstrap-components.yaml`](../../workspace/config/bootstrap-components.yaml): tool component registry
- [`workspace/config/workspace-clones.yaml`](../../workspace/config/workspace-clones.yaml): workspace repository registry
- [`workspace/config/install-aux.yaml`](../../workspace/config/install-aux.yaml): auxiliary feature registry
- [`workspace/config/install-defaults.yaml`](../../workspace/config/install-defaults.yaml): non-interactive defaults
- [REQ-STORAGE](../../projects/WORKSPACE-DATAOPS/docs/requirements/REQ-STORAGE.md): storage ownership
- [REQ-DEPLOYMENT](../../projects/WORKSPACE-CI/docs/requirements/REQ-DEPLOYMENT.md): sealed CI publication
- [REQ-BOOT-LAYOUT](../../projects/WORKSPACE-CI/docs/requirements/REQ-BOOT-LAYOUT.md): boot directory contract

---

## 1. Purpose & Scope

### 1.1 Purpose

Define one installer lifecycle with explicit stages, registries, and ordering.
Every install action MUST belong to exactly one stage.

### 1.2 Ownership

- **WORKSPACE-VM OWNS** the installer entry points, registries, ordering, and
  auxiliary selection.
- **WORKSPACE-CI OWNS** `/opt/workspace-ci` publication and boot artifacts.
- **WORKSPACE-DATAOPS OWNS** storage scripts, the storage-locations seam, and
  service targets.
- **WORKSPACE-GUARD OWNS** root-owned hooks, guard installation, and host
  exemptions.

### 1.3 Out of Scope

- llama/GPU installation (owned by [REQ-LLAMA-SETUP-TUI](REQ-LLAMA-SETUP-TUI.md)).
- QEMU installation (owned by [REQ-VM-HYPERVISOR](REQ-VM-HYPERVISOR.md)).
- VPN client installation (owned by [REQ-OPENVPN](REQ-OPENVPN.md)).
- Partitioning, `mkfs`, and disk destruction. These stay operator-run.

## 2. Lifecycle Stages

| Stage | Entry point | Authority | MUST NEVER |
|-------|-------------|-----------|------------|
| Prerequisite | manual clone + `make core` | checkout owner | write root-owned paths |
| User install | `make install`, `make install-ci` | checkout owner | install hooks, mount disks, write `/opt` |
| Root bootstrap | `sudo make init` | root | write checkout boot dirs as root |
| Auxiliary reapply | `make install-aux` | checkout owner | run root-only actions |

### FR-1: Cold-start ordering

| ID | Requirement |
|----|-------------|
| FR-1.1 | The installer MUST fail with a named error when `/opt/workspace-ci` is absent, naming the CI bootstrap command. |
| FR-1.2 | The lifecycle MUST NOT claim a cold-host `make install` path that needs an artifact produced by `sudo make init`. |
| FR-1.3 | `make core` MUST create `.boot-linux/bin/python` before `bootstrap-repos` runs. |
| FR-1.4 | `make sync-package` MUST run only after the mandatory `workspace-dataops` clone exists. |
| FR-1.5 | `sudo make init` MUST verify `projects/WORKSPACE-CI` exists and MUST NOT run `ensure-repos` as root. |

### FR-2: Stage boundaries

| ID | Requirement |
|----|-------------|
| FR-2.1 | `make install` and `make install-ci` MUST remain non-root. |
| FR-2.2 | Root-only actions MUST live in `init-root`. |
| FR-2.3 | The root stage MUST NOT write the checkout-owned `.boot-linux` directory. |
| FR-2.4 | The user stage MUST NOT install hooks or write `/opt/workspace-ci`. |
| FR-2.5 | The `hooks` component MUST NOT be installable from the user stage. |
| FR-2.6 | Agent-scope auxiliary actions invoked by the root stage MUST run as the checkout owner (`SUDO_USER`). |

### FR-3: Registries

| ID | Requirement |
|----|-------------|
| FR-3.1 | Tool components MUST come from `workspace/config/bootstrap-components.yaml`. |
| FR-3.2 | Workspace repositories MUST come from `workspace/config/workspace-clones.yaml`. |
| FR-3.3 | Auxiliary features MUST come from `workspace/config/install-aux.yaml`. |
| FR-3.4 | Non-interactive selections MUST come from `workspace/config/install-defaults.yaml`. |
| FR-3.5 | Unknown registry names MUST fail the install, not be skipped. |

### FR-4: Auxiliary features (V1)

| ID | Requirement |
|----|-------------|
| FR-4.1 | The host stage MUST offer the storage-locations seam. |
| FR-4.2 | The host stage MUST offer backup mount and boot persistence. |
| FR-4.3 | The host stage MUST offer fast-storage provisioning in dry-run first. |
| FR-4.4 | The host stage MUST offer the copy-only storage migration. |
| FR-4.5 | The host stage MUST offer hang-evidence diagnostics. |
| FR-4.6 | The host stage MUST offer AgentCI installation and verification. |
| FR-4.7 | The host stage MUST offer DATAOPS service profile selection. |
| FR-4.8 | Auxiliary status MUST be detected from files, mounts, or commands before selection. |

### FR-5: Storage

| ID | Requirement |
|----|-------------|
| FR-5.1 | The installer MUST write `workspace/config/storage-locations.yaml` through the DATAOPS seam writer. |
| FR-5.2 | The seam file MUST be git-ignored. |
| FR-5.3 | Root storage actions MUST run before agent migration. |
| FR-5.4 | `storage-provision` MUST run in dry-run before an apply run. |
| FR-5.5 | `storage-migrate` MUST run as the checkout owner. |
| FR-5.6 | The installer MUST NOT execute `wipefs`, `parted`, `fdisk`, or `mkfs`. |

### FR-6: Non-interactive mode

| ID | Requirement |
|----|-------------|
| FR-6.1 | `sudo make init` MUST accept a defaults file for unattended runs. |
| FR-6.2 | `make install-ci` MUST remain non-interactive. |
| FR-6.3 | Non-interactive runs MUST be idempotent. |
| FR-6.4 | A failed auxiliary action MUST be reported and MUST exit non-zero. |

### FR-7: Ordering

| ID | Requirement |
|----|-------------|
| FR-7.1 | Public targets MUST NOT rely on Make prerequisite order under `-j`. |
| FR-7.2 | Repositories MUST be cloned before extension registration. |
| FR-7.3 | `.venv` MUST exist before extension registration and auxiliary Python actions. |
| FR-7.4 | System packages MUST be installed before component and storage actions. |
| FR-7.5 | `/opt/workspace-ci` MUST be deployed before guard installation. |
| FR-7.6 | Guard installation MUST run after mandatory repositories exist. |

## 3. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1.1 | Preserve the 512-line source limit. |
| NFR-1.2 | No new Python dependency. |
| NFR-1.3 | Auxiliary registry parsing uses Pydantic, matching existing loaders. |
| NFR-1.4 | Every action is idempotent. |
| NFR-1.5 | Every failure names the failing action and a remediation command. |
| NFR-1.6 | Shell actions use `#!/bin/bash` and `set -euo pipefail`. |

## 4. Acceptance Criteria

- **AC-1** `sudo make init AUX_DEFAULTS=<file>` runs root and agent auxiliary actions without prompts.
- **AC-2** `sudo make init` shows one host-configuration TUI.
- **AC-3** The storage seam is written and git-ignored.
- **AC-4** `ws-backup` mount and persist actions are root-gated.
- **AC-5** `storage-migrate` is agent-gated and never runs before root storage actions.
- **AC-6** `make install` never attempts hooks or root writes.
- **AC-7** Unknown component, repo, or auxiliary IDs fail the run.
- **AC-8** `make install-ci` and `make install-aux` remain non-root.
- **AC-9** Unit tests cover registry loading, validation, ordering, and defaults.
- **AC-10** Documentation index links both REQ and SPEC.
