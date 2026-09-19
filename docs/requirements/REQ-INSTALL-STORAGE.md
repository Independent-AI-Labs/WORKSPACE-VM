# Requirements: Install-Time Storage Planning Step

**Document ID:** WS-REQ-INSTALL-STORAGE-v0.1
**Status:** Draft , pending operator review
**Parent Docs:** docs/OPS-FAST-STORAGE.md, workspace/scripts/bootstrap_installer.py, workspace/config/install-defaults.yaml
**Last Updated:** 2026-09-16

## 1. Purpose

`make install` (and its non-interactive twin `install-ci`) currently lands every
component on the root filesystem without asking where bulk data should live.
On this host the root device is LUKS-encrypted, so every build IO additionally
pays dm-crypt overhead, and the fast-storage topology that OPS-FAST-STORAGE.md
documents (`/mnt/ws-fast` RAID0 scratch + backup location) was provisioned by a
one-off operator script that exists nowhere in the repo.

This document specifies a new **pre-component-selection storage planning step**
in the installer TUI that detects the encryption state of the checkout and lets
the user confirm or override two storage locations before any component runs.

## 2. Decision Log (auto-filled, verified this session)

- Installer entry: `workspace/scripts/bootstrap_installer.py` (493 lines,
  TUI via `select_workspace_repos()`), CI path `--defaults workspace/config/install-defaults.yaml`.
- This host's checkout sits on LUKS: `findmnt` source `/dev/mapper/ubuntu--vg-ubuntu--lv`
  (ext4) → LVM → `dm_crypt-0` (lsblk TYPE=`crypt`, FSTYPE=`crypto_LUKS`) → nvme1n1p3.
  Detection is fully rootless (findmnt + lsblk ancestry walk).
- Live fast-storage tree (`/mnt/ws-fast`): `caches/ containers/ diag/ models/ qemu/ swap/`.
  Consumers with hardcoded paths today: `hang-evidence-sampler.sh` (diag),
  `~/.config/containers/storage.conf` (graphroot), HF model env, nspawn disk, QEMU overlays.
- Incident finding 2026-09-14: the backup bind mount pointed at the **same device**
  as fast storage , zero added failure tolerance. Backup-on-same-device must be
  detected and warned, never accepted quietly.
- Provisioning of the live tree was a `/tmp` one-off (`enable-fast-storage.sh`);
  nothing in the repo can reproduce it. This REQ codifies it.
- House rules: docs-first (this file), no destructive automation (formatting stays
  operator-run), TUI must have a declarative CI equivalent (install-defaults.yaml).

## 3. Scope

### In Scope (v1)

- Storage planning phase in the installer TUI, **before** component selection.
- Rootless encryption detection of the checkout's backing device.
- Two user-facing decisions: fast storage location, backup location.
- One machine-local recorded config that consumers read.
- Declarative equivalents in `install-defaults.yaml` for `install-ci`.
- Same-device warning for the backup location.

### Out of Scope (v1)

- Auto-formatting, partitioning, RAID/LVM composition , operator-run only.
- Migrating existing data between locations (containers store, models).
- Encryption provisioning (creating LUKS volumes).
- Network/remote backup targets.

## 4. Requirements

### Detection

- **R1 , Checkout encryption detection.** Before the component menu renders, the
  installer resolves the mount source of the checkout root via `findmnt`, walks
  the device ancestry via `lsblk`, and reports **encrypted / not encrypted**
  (a node with TYPE `crypt` or FSTYPE `crypto_LUKS` anywhere in the chain).
  Detection uses rootless commands only; failure to resolve must abort the step
  with a named error, never guess.
- **R2 , Detection drives the recommendation.** When the checkout is encrypted,
  the TUI explains that builds pay dm-crypt IO overhead on root and recommends a
  dedicated fast location; when not encrypted, the step still runs but the
  rationale line changes (capacity/isolation instead of IO overhead).

### TUI Step

- **R3 , Placement.** The step runs after installer start and before
  `select_workspace_repos()`; its outcome is available to later phases.
- **R4 , Fast storage prompt.** Free-text path with default `/mnt/ws-fast`
  (mount name `ws-fast`). Validated: absolute path; if the path exists it must
  be a mounted filesystem or a directory the user can write; free space is shown.
- **R5 , Backup prompt.** Free-text path with default `/mnt/ws-backup`
  (mount name `ws-backup`). Same validation as R4.
- **R6 , Same-device guard.** If the backup path resolves to the same block
  device as the fast path, the TUI shows the 2026-09-14 finding (a backup that
  dies with the data it protects) and requires explicit confirmation to proceed.
- **R7 , Existing topology pre-fill.** When a recorded config already exists
  (R8), its values pre-fill the prompts; accepting them is a no-change pass.
- **R8 , Recorded config.** The chosen locations are written to a machine-local
  YAML (not committed): `workspace/config/storage-locations.yaml` with schema
  `fast: <path>`, `backup: <path>`. This file is the single seam consumers
  (sampler diag dir, container graphroot, model dir, qemu dir, caches) read;
  hardcoded consumer paths are migrated to read it in the implementation SPEC.

### CI / Non-Interactive

- **R9 , Declarative parity.** `install-defaults.yaml` gains a `storage:` section
  (`fast:`, `backup:`). Absent section = step skipped, no locations recorded
  (current behaviour). Present section = validated exactly as R4-R6 (the
  same-device warning aborts CI unless `allow_same_device: true` is set).

### Provisioning Boundary

- **R10 , Never destructive.** The installer creates missing directories under an
  already-mounted filesystem and records the config. Mounting, fstab entries,
  mkfs, and RAID assembly are reported to the user as operator steps (exact
  commands printed), matching the trusted-input security posture of
  REQ-AGENT-POLICY.

## 5. Acceptance Criteria

- **AC-1** On this host, `make install` reports the checkout as encrypted and
  names the chain (`/dev/mapper/ubuntu--vg-ubuntu--lv` → `dm_crypt-0`).
- **AC-2** On this host (already provisioned), the step pre-fills
  `/mnt/ws-fast` + backup path from the recorded config and a no-change pass
  writes nothing.
- **AC-3** Pointing the backup prompt at a path on the same device as fast
  storage shows the warning and requires explicit confirmation (TUI) or
  `allow_same_device: true` (CI).
- **AC-4** `install-ci` with a `storage:` section records the same config the
  TUI would, with zero prompts.
- **AC-5** `workspace/config/storage-locations.yaml` is gitignored and its
  schema documented in OPS-FAST-STORAGE.md.
- **AC-6** Detection failure (findmnt/lsblk unresolvable) aborts with a named
  error and remediation hint.

## 6. Risks and Constraints

- Consumers currently hardcode `/mnt/ws-fast`; the SPEC must enumerate every
  consumer before the seam lands, or the config will drift from reality.
- The step must not add measurable startup delay to `install-ci` when the
  section is absent (CI hot path).

## 7. Open Questions

- Should an existing status surface (`init-check` or `diagnostics-status`) gain
  a storage sub-check (mounted, free-space floor, backup device distinctness) in
  the same change or a follow-up?
