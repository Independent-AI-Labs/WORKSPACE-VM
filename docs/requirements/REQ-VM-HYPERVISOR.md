# VM Hypervisor Extension - Enterprise Requirements Specification

**Document ID:** WS-REQ-VM-HYPERVISOR-v1.0
**Status:** Draft
**Date:** 2026-10-23
**Classification:** Internal - Enterprise
**Specification:** [SPEC-VM-HYPERVISOR](../specifications/SPEC-VM-HYPERVISOR.md)
**Authors:** Workspace Engineering
**References:**
- [SPEC-VM-HYPERVISOR](../specifications/SPEC-VM-HYPERVISOR.md) (Technical Specification)
- [REQ-OPENVPN](REQ-OPENVPN.md) (VM network modes - Podman backend)
- [REQ-ANDROID-WORKSPACE](REQ-ANDROID-WORKSPACE.md) (native Android package and WSL or chroot developer path)
- [REQ-NATIVE-VM-PACKAGES](REQ-NATIVE-VM-PACKAGES.md) (native Windows, macOS, Android, and Linux packages)
- [workspace/config/vm-template.yaml](../../workspace/config/vm-template.yaml) (VM config reference)
- [projects/WORKSPACE-GUARD/docs/requirements/REQ-SANDBOX.md](../../projects/WORKSPACE-GUARD/docs/requirements/REQ-SANDBOX.md) (Guard install / cap E2E authority)
- [AGENTS.md](../../AGENTS.md) (Universal Agent Rules)

---

## 1. Scope

This document specifies functional and non-functional requirements for extending
`make vm` with a **dual isolation backend**: rootless **Podman** (existing) and
**QEMU** (new). Both backends share the same YAML configuration surface, UUID
lifecycle under `.vms/<uuid>/`, and `components` → `make install-ci` install
layer - but use different hypervisor drivers underneath.

The feature provides:

- **Backward-compatible default** - `isolation.backend: podman` preserves all
 existing agent-container behavior
- **Hardware VM boundary** - `isolation.backend: qemu` runs a full Linux guest
 with its own kernel so host filesystem and kernel guardrails cannot be
 modified by guest workloads
- **Authoritative guard testing** - WORKSPACE-GUARD capability, `setcap`, and
 `chattr` E2E SHALL run only inside QEMU guests
- **Cross-platform engine strategy** - QEMU (GPL-2.0) with per-host accelerator
 auto-selection and TCG software emulation as the universal engine

**In scope (product target):**

- REQ/SPEC documentation and a maintained support matrix
- `isolation.backend` schema extension in `workspace/types/vm.py`
- `workspace/cli/hypervisor/` module with `IsolationBackend` protocol
- `QemuBackend` persistent VMs on native Linux and macOS hosts
- `PodmanBackend` thin wrapper with no behavioral change
- Production QEMU lifecycle: create, start, stop, rebuild, sync, delete
- Persistent QCOW2 disks with protected delete semantics
- Snapshot, export, and import for backup and restore
- Systemd autostart for QEMU VMs
- QEMU day-2 configuration parity where the backend can support it
- QEMU network, web UI, credentials, SSH, files, mounts, and environment parity
- Authoritative WORKSPACE-GUARD capability and policy-matrix E2E inside QEMU
- Windows and Android developer access through the rootless bootstrap path on
  local Debian or Ubuntu under WSL or chroot
- E2E coverage for every supported production feature
- Documentation tests that keep commands, status, and limitations current

**Out of scope for this product target:**

- iOS host support
- Replacing or demoting rootless Podman for everyday agent development
- Native Windows, Android, and macOS end-user packages
- Native Windows WHPX bundle and native Android client packaging
- Modified QEMU builds and distribution outside the pinned boot bundle

**Platform delivery model:**

- Linux and macOS are native QEMU hosts.
- Windows and Android are supported through the rootless bootstrap path on a
  local Debian or Ubuntu environment under WSL or chroot.
- Native Windows, Android, and macOS end-user packages are separate workstreams
  and SHALL consume the same backend contract when delivered.

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Host** | The developer machine running `make vm` (macOS, Linux, Windows, or Android) |
| **Guest** | The isolated environment where agents and tests run |
| **Podman backend** | Rootless OCI container path via existing `vm_build.py` / `vm_manager.py` |
| **QEMU backend** | Full hardware-emulated or accelerated Linux VM via `qemu-system-*` |
| **Isolation backend** | The hypervisor driver selected by `isolation.backend` in VM YAML |
| **VM boundary** | QEMU guest with separate kernel - guest writes do not affect host `/` |
| **TCG** | QEMU Tiny Code Generator - software CPU emulation, available on every host |
| **Accelerator** | Host-specific QEMU accel: `kvm` (Linux), `hvf` (macOS), `whpx` (Windows) |
| **Boot directory** | Workspace-local directory containing pinned tool binaries. |
| **Base image** | Shared Ubuntu cloud image under `.vms/_base/` |
| **Overlay disk** | Per-VM QCOW2 overlay at `.vms/<uuid>/disk.qcow2` |
| **Cloud-init seed** | FAT/ISO seed image injecting SSH keys and first-boot provisioning |
| **Release gate** | WORKSPACE-GUARD cap/kernel E2E required inside QEMU; Darwin Podman is not sufficient |
| **Aggregation** | GPL applies to QEMU binaries distributed with the workspace; workspace Python code invokes QEMU as a separate process and does not link `libqemu` |
| **Pins manifest** | `res/qemu-pins.yaml` - pinned upstream version, checksums, and source URLs per platform |
| **Firmware bundle** | EDK2/OVMF blobs required for `virt`/`q35` machines; separate license from QEMU |
| **Persistent VM** | QEMU VM whose QCOW2 overlay, state, and metadata survive stop, host reboot, and VM restart |
| **Snapshot** | Internal QCOW2 snapshot of a stopped or quiesced VM disk |
| **Export** | Portable QCOW2 plus metadata bundle for backup or transfer |
| **Import** | Restore of a previously exported VM bundle into the local VM store |
| **Autostart** | Systemd user or system mechanism that starts a persistent VM on boot or login |
| **Rootless bootstrap path** | Debian or Ubuntu environment under WSL or chroot that runs the same bootstrap, QEMU, and VM CLI as a native Linux host |

---

## 3. Problem Statement

Rootless Podman on macOS and Windows runs inside a lightweight VM (podman-machine)
or user-namespace emulation. Container isolation is sufficient for everyday agent
development but **does not** provide a true kernel boundary for validating
WORKSPACE-GUARD install procedures (`setcap`, `chattr +i`, file capabilities,
`prctl` behavior).

```
host → QEMU Linux guest → agent / guard install / tests
```

Podman on macOS and `cargo test` on Darwin do not provide a separate guest kernel.
Guard install and cap E2E must run inside a QEMU guest so changes apply to guest
`/`, not host `/`.

---

## 4. Functional Requirements

### FR-1: Dual Backend Selection

**FR-1.1 (REQ-VMH-001)** `VMConfig` SHALL support `isolation.backend: podman | qemu`.
The default SHALL be `podman` so existing configs and `vm-template.yaml` remain
valid without modification.

**FR-1.2** `vm_manager.create` and related lifecycle entry points SHALL dispatch to
the backend implementation selected by `isolation.backend`.

**FR-1.3** `make vm list`, `status`, `start`, `stop`, `delete`, `shell`, `exec`,
`logs`, `config`, `rebuild`, and `sync` SHALL be backend-aware. QEMU parity is
required for every feature in SPEC §8, or the feature SHALL fail with a typed
validation error that names the unsupported field.

### FR-2: Podman Backend Preservation

**FR-2.1 (REQ-VMH-002)** When `isolation.backend: podman`, the system SHALL preserve
existing rootless security defaults from `VMSecurityConfig`:

- `cap_drop: ["ALL"]`
- `no_new_privileges: true`
- `read_only_rootfs: true`
- `purge_sudo: true` (default)

**FR-2.2 (REQ-VMH-008)** Podman backend SHALL continue to support all existing
`network.mode` values including `openvpn` per [REQ-OPENVPN](REQ-OPENVPN.md).

**FR-2.3** Podman backend SHALL NOT require QEMU binaries or base disk images.

**FR-2.4** Existing E2E security tests in `tests/e2e/test_vm_security.py` SHALL
continue to pass unchanged for Podman VMs.

### FR-3: QEMU Backend - Guest Isolation

**FR-3.1 (REQ-VMH-003)** When `isolation.backend: qemu`, the system SHALL boot a
full Linux guest (Ubuntu 22.04 or 24.04 LTS) with its own kernel. Guest operations
SHALL NOT modify the host root filesystem.

**FR-3.2** QEMU guest provisioning SHALL use cloud-init for first-boot SSH access,
user creation, and optional `make install-ci` invocation.

**FR-3.3** Per-VM storage SHALL use a QCOW2 overlay backed by a shared base image
so the base remains pristine across VM lifecycles.

**FR-3.4 (REQ-VMH-009)** Host bind mounts into QEMU guests SHALL use
**read-only** virtio-9p/virtfs shares. Writable host mounts SHALL NOT be used for
guard-test surfaces in v1.

**FR-3.6 (REQ-VMH-012)** Guest provisioning SHALL combine the RO virtio-9p share
with **selective rsync** into guest disk (`/opt/workspace`). The host tree is
never written through the mount; rsync copies only the paths required by the
active profile (see SPEC §6.6). Full `install-ci` runs against the guest-local
copy, not the RO mount.

**FR-3.5** QEMU backend SHALL write lifecycle artifacts under `.vms/<uuid>/`:
`qemu.pid`, `ssh_port`, `disk.qcow2`, `cloud-init/`, and `vm.yaml` (same as Podman).

### FR-4: Shared Install Layer

**FR-4.1 (REQ-VMH-004)** Both backends SHALL use the same `components:` list and
`extra_apt:` fields, passed to `make install-ci` inside the guest environment.

**FR-4.2** `provider`, `credentials`, `ssh`, `files`, `sync`, `mounts`, `env`,
`web_ui`, `network`, `security`, and `resources` fields SHALL be supported by
both backends. A field that cannot be implemented safely for a backend SHALL
fail schema validation with a remediation message. Silent ignore is forbidden.

**FR-4.3** `vm-poc-qemu.yaml` MAY boot with SSH only (no `install-ci`). Full
`install-ci` inside QEMU guests is required for `vm-full-ci-qemu.yaml` and the
authoritative WORKSPACE-GUARD gate (`make test-vm-guard`).

### FR-5: QEMU Accelerator Selection

**FR-5.1 (REQ-VMH-005)** QEMU backend SHALL auto-select accelerator when
`isolation.qemu.accel: auto`:

| Host OS | Primary | Fallback |
|---------|---------|----------|
| Linux | `kvm` | `tcg` |
| macOS | `hvf` | `tcg` |
| Windows | `whpx` | `tcg` |
| Android | `tcg` only | - |

**FR-5.2** Explicit `accel` values (`kvm`, `hvf`, `whpx`, `tcg`) SHALL override
auto-detection. Invalid accel for host SHALL fail at create time with a clear error.

**FR-5.3** QEMU binary resolution SHALL use exactly one source:
`<boot-dir>/bin/qemu-system-<arch>`. When it is missing, the command SHALL fail
with bootstrap instructions. PATH selection is forbidden for production paths.

### FR-6: Platform Support

**FR-6.1 (REQ-VMH-006)** QEMU SHALL support native Linux and macOS developer hosts.

**FR-6.2 (REQ-VMH-013)** Windows and Android developers SHALL be supported through
the rootless bootstrap path on a local Debian or Ubuntu environment under WSL or
chroot. That path SHALL run the same bootstrap, QEMU backend, CLI, and E2E gates
as native Linux. Native Windows WHPX, native Android packaging, and macOS
end-user packages are separate requirements tracked outside this document.

**FR-6.3 (REQ-VMH-010)** iOS SHALL be explicitly out of scope for v1.

**FR-6.4** `isolation.qemu.guest_arch` SHALL support `aarch64` and `x86_64`. The
default SHALL match host architecture where practical.

### FR-7: WORKSPACE-GUARD Integration

**FR-7.1 (REQ-VMH-007)** Authoritative WORKSPACE-GUARD capability and kernel E2E
(`scripts/podman/e2e-capability.sh`, Tier 3 policy matrix on real caps) SHALL
run only inside `isolation.backend: qemu` guests.

**FR-7.2** WORKSPACE-GUARD `make test-podman` SHALL remain a **dev sanity check** gate
(Rust unit/integration inside container). It SHALL NOT be demoted or removed.

**FR-7.3** WORKSPACE-GUARD documentation SHALL reference WORKSPACE-VM QEMU gate
(`make test-vm-guard`) as the authoritative cap/kernel sign-off path.

**FR-7.4** A guest script (`WORKSPACE-GUARD/scripts/qemu/e2e-guest.sh`) SHALL run
`e2e-capability.sh` and `e2e-policy-matrix.sh` inside QEMU guests. Podman Tier 3
remains a dev sanity check only.

### FR-8: Lifecycle and CLI

**FR-8.1** `vm create <config.yaml>` with `isolation.backend: qemu` SHALL:
allocate UUID, prepare disk overlay, generate cloud-init seed, spawn QEMU,
wait for SSH health, apply guest configuration, and print connection details.
Creation SHALL be resumable after a provisioning failure and SHALL remove
partial artifacts only when the operator requests it.

**FR-8.2** `vm stop <id>` SHALL request guest ACPI shutdown through QMP, wait
for the guest to power down, then use SIGTERM and finally SIGKILL. The command
SHALL NOT report success until the process has exited.

**FR-8.3** `vm delete <id>` SHALL terminate QEMU and preserve the overlay and
metadata by default. `vm delete <id> --purge` SHALL remove the overlay and
metadata. The shared base image in `_base/` SHALL always be retained.

**FR-8.4** `vm shell <id>` for QEMU SHALL connect via SSH to the forwarded
localhost port with the per-VM key.

**FR-8.5** `vm rebuild <id>` for QEMU SHALL regenerate cloud-init and guest
configuration, preserve the overlay by default, and offer `--fresh` for a new
overlay. Rebuild SHALL re-run the configured provisioning profile.

**FR-8.6** `vm sync <id>` for QEMU SHALL apply `sync` rules over SSH to the guest
workspace. It SHALL support merge, overwrite, skip, and exclude semantics.

**FR-8.7** `vm status` and `vm list` SHALL report QEMU state without trusting a
stale PID alone. State SHALL include process identity, SSH port, disk size,
provisioning profile, and persistent or ephemeral mode.

### FR-9: GPL compliance and code separation

**FR-9.1 (REQ-VMH-011)** WORKSPACE-VM orchestration code (Python, shell) SHALL invoke
QEMU only as an **external process** (`subprocess` / `exec`). It SHALL NOT link against
`libqemu`, `libqemuutil`, or other QEMU libraries. No QEMU headers in workspace builds.

**FR-9.2** QEMU binaries distributed or symlinked under `<boot-dir>/bin/` and
`<boot-dir>/share/qemu/` are GPL-2.0 artifacts. They SHALL remain physically separate
from workspace-compiled binaries (guard, Python extensions, Rust tools).

**FR-9.3** When QEMU binaries are vendored or symlinked into the boot directory, the
bootstrap SHALL install:

- `COPYING` / `LICENSE` (GPL-2.0 full text) under `<boot-dir>/share/qemu/`
- `NOTICE` listing QEMU version, download URL, and corresponding source URL
- `res/qemu-pins.yaml` entry matching the installed version

**FR-9.4** Modified QEMU builds are out of scope for v1. If introduced later, modified
source SHALL be published per GPL §2 before distribution.

**FR-9.5** Guest disk images (Ubuntu cloud), cloud-init seeds, and firmware blobs (EDK2)
are separate artifacts with their own licenses. They SHALL NOT be compiled into workspace
binaries.

**FR-9.6** Native Android packaging SHALL use the same rule: JNI launches a
repackaged upstream QEMU binary; workspace Kotlin or Java code does not link QEMU
as a library. Native Android packaging is a separate delivery workstream tracked
in [REQ-NATIVE-VM-PACKAGES](REQ-NATIVE-VM-PACKAGES.md).

### FR-10: Bootstrap and version pinning

**FR-10.1 (REQ-VMH-012)** QEMU SHALL be a first-class bootstrap component
(`bootstrap-components.yaml` entry `qemu`) installed by `make install-qemu` /
`workspace/scripts/bootstrap/bootstrap_qemu.sh`.

**FR-10.2** Bootstrap SHALL install into the platform boot directory:

| Artifact | Linux path | macOS path |
|----------|------------|------------|
| `qemu-system-aarch64` | `.boot-linux/bin/` | `.boot-macos/bin/` |
| `qemu-system-x86_64` | `.boot-linux/bin/` | `.boot-macos/bin/` |
| `qemu-img` | `.boot-linux/bin/` | `.boot-macos/bin/` |
| EDK2 `QEMU_EFI.fd` (aarch64) | `.boot-linux/share/qemu/firmware/` | `.boot-macos/share/qemu/firmware/` |
| OVMF (x86_64, optional) | same | same |
| GPL notice bundle | `.boot-*/share/qemu/LICENSE`, `NOTICE` | same |

**FR-10.3** `res/qemu-pins.yaml` SHALL record for each platform: `version`, `sha256`,
`download_url` (or package name), `source_url` (QEMU release tarball), and
`firmware_packages` (apt/brew package names).

**FR-10.4** Linux bootstrap SHALL prefer **symlinks to distro packages** when versions
match the pin file. macOS SHALL symlink from Homebrew. When the installed distro
version differs from the pin, bootstrap SHALL use the pinned tarball and report the
selection reason.

**FR-10.5** Boot-dir binaries SHALL be required on all hosts. Missing binaries SHALL
produce an explicit error with bootstrap instructions; host-PATH selection is prohibited.

**FR-10.6** `config/system-deps.yaml` SHALL list host tools required by QEMU backend
that are not QEMU itself: `cloud-image-utils` (`cloud-localds`), and on Linux
`qemu-utils` when not fully bootstrapped.

### FR-11: Guest boot assets

**FR-11.1** AArch64 guests using `-machine virt` SHALL boot with EDK2 firmware from
the firmware bundle (`-bios` or pflash drives per SPEC).

**FR-11.2** Ubuntu base images SHALL be downloaded to `.vms/_base/` with SHA256
verification against `res/qemu-pins.yaml`.

**FR-11.3** Cloud-init seeds SHALL be built with `cloud-localds` (preferred) or
`mkisofs`/`genisoimage`; seed format SHALL be `nocloud` on a virtio block device.

**FR-11.4** Linux hosts using KVM SHALL document `/dev/kvm` group membership as a
prerequisite; macOS HVF requires no extra entitlement for `qemu-system-*`.

### FR-12: Persistent Storage And Data Safety

**FR-12.1** A persistent VM SHALL retain its QCOW2 overlay, guest packages,
workspace copy, and service state across stop and start.

**FR-12.2** Host reboot SHALL NOT delete persistent VM state. A later `vm start`
SHALL recover and validate the same overlay.

**FR-12.3** E2E cleanup and orphan reclamation SHALL skip VMs marked persistent.
Only ephemeral test VMs may be reclaimed automatically.

**FR-12.4** `vm delete` without `--purge` SHALL be reversible. The operator SHALL
be able to restart or export the VM after an accidental delete of registration.

**FR-12.5** Base image corruption or missing backing files SHALL fail with an
explicit error. The backend SHALL NOT create a blank disk.

### FR-13: Snapshot, Export, And Import

**FR-13.1** `vm snapshot <id> <name>` SHALL create a QCOW2 snapshot or an
equivalent disk checkpoint while the VM is stopped or quiesced.

**FR-13.2** `vm snapshot list <id>` and `vm snapshot delete <id> <name>` SHALL
list and remove snapshots with clear errors for missing names.

**FR-13.3** `vm export <id> <path>` SHALL produce a portable QCOW2 plus metadata
bundle. Export SHALL NOT include host secrets or the shared base image.

**FR-13.4** `vm import <path>` SHALL restore an exported bundle as a new VM with
a new UUID and a validated config.

**FR-13.5** Snapshot, export, and import SHALL preserve enough state for full-ci
toolchains, workspace content, and guest service configuration.

### FR-14: Autostart

**FR-14.1** `vm autostart enable <id>` SHALL install a systemd user unit that
starts the persistent VM after login.

**FR-14.2** `vm autostart disable <id>` SHALL remove the unit and leave the VM
disk untouched.

**FR-14.3** Autostart SHALL be idempotent and SHALL fail clearly when systemd
user services are unavailable.

**FR-14.4** Autostart SHALL NOT start ephemeral E2E VMs.

### FR-15: Config Parity

**FR-15.1** `files` SHALL copy host files or directories into the guest
workspace with explicit source and destination validation.

**FR-15.2** `mounts` SHALL add read-only virtio-9p shares for host paths.

**FR-15.3** `env` SHALL apply to guest login and managed service environments.

**FR-15.4** `provider` SHALL generate guest OpenCode provider configuration.

**FR-15.5** `credentials` SHALL support none, clone, and API modes with no
credential material in logs.

**FR-15.6** `ssh` SHALL support none, inherit, and custom modes for guest keys
and configuration.

**FR-15.7** `web_ui` SHALL start a guest OpenCode web service and expose it on
localhost with authentication.

**FR-15.8** `security` fields SHALL be mapped to guest controls or rejected at
validation time when safe parity is impossible.

### FR-16: Network Parity

**FR-16.1** `network.mode: none` SHALL permit SSH forwarding only and SHALL
block guest egress to external networks.

**FR-16.2** `network.mode: bridge` SHALL provide a bridged interface on Linux
hosts with the configured policy.

**FR-16.3** `network.mode: openvpn` SHALL run the OpenVPN client inside the guest
or through a host netns, with an explicit mode choice.

**FR-16.4** `network.mode: host` SHALL be rejected for QEMU with a clear error
because it has no safe direct equivalent.

**FR-16.5** `network.policy: proxy` SHALL configure guest proxy environment and
enforce the configured whitelist where supported.

---

## 5. Non-Functional Requirements

**NFR-1** No breaking change to existing Podman-only workflows. Default backend
is `podman`; all current tests and configs pass without edits.

**NFR-2** No implicit alternate selection is permitted for a missing QEMU binary, base image, or failed
accelerator probe - surface explicit errors with bootstrap hints.

**NFR-3** No untyped dicts with object-typed values in new Python code; use typed models per AGENTS.md.

**NFR-4** Shell scripts SHALL use `#!/bin/bash`, `set -euo pipefail`, and
`source ... || exit 1`.

**NFR-5** All new source files (non-markdown) SHALL remain under 512 lines.

**NFR-6** QEMU E2E tests SHALL skip with an explicit reason when the QEMU binary,
firmware, or accelerator is unavailable. A skip SHALL NOT be reported as a pass.

**NFR-7** Base Ubuntu image download SHALL be cached under `.vms/_base/` and
SHALL NOT be re-downloaded on every `vm create`.

**NFR-8** Guest SSH health wait SHALL reuse the existing `_wait_healthy` timeout
pattern from `vm_core.py` (adapted for SSH probe).

**NFR-9** Hypervisor Python modules SHALL stay below the 512-line file limit by splitting
`qemu_argv.py`, `qemu_images.py`, and `qemu_spawn.py` rather than growing a monolith.

**NFR-10** `qemu_backend.py` SHALL contain no GPL-licensed code; only MIT/Apache-compatible
workspace code that constructs argv and manages subprocess lifecycle.

**NFR-11** WSL and chroot environments SHALL run the same Linux E2E gates as a
native Linux host.

**NFR-12** Documentation SHALL state current behavior separately from target
behavior. A roadmap item SHALL NOT be described as implemented.

**NFR-13** Every supported production feature SHALL have an E2E test. Every
unsupported config field SHALL have a rejection test.

**NFR-14** Persistent VM cleanup and E2E teardown SHALL be data-safe by default.
No automated command may delete a persistent disk without explicit operator intent.

---

## 6. Backend Selection Guide

| Use case | Backend |
|----------|---------|
| Daily agent dev, opencode web UI, fast iteration | **podman** |
| OpenVPN container / netns modes | **podman** |
| WORKSPACE-GUARD `setcap` / `chattr` install test | **qemu** |
| macOS host - agent must not touch host kernel | **qemu** |
| Windows or Android developer host | **qemu** through WSL or chroot on Debian or Ubuntu |
| Native Windows, Android, macOS, or Linux package | separate package workstream |
| CI Rust / unit tests only | podman or bare Linux (existing Tier 1) |

---

## 7. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | `REQ-VM-HYPERVISOR.md` and `SPEC-VM-HYPERVISOR.md` committed and cross-linked |
| AC-2 | `vm-template.yaml` documents `isolation` block; default `backend: podman` |
| AC-3 | Existing Podman `vm create` with `vm-template.yaml` behavior unchanged |
| AC-4 | `vm create workspace/config/vm-poc-qemu.yaml` boots QEMU guest on Linux or macOS |
| AC-5 | SSH to forwarded port succeeds; `uname -a` shows Linux guest kernel |
| AC-6 | Host `/` is not modified by guest create / SSH / sanity-check commands |
| AC-7 | `tests/e2e/test_vm_qemu_poc.py` passes on Linux/macOS with QEMU present; skips otherwise |
| AC-8 | `tests/e2e/test_vm_security.py` Podman tests still pass |
| AC-9 | Unit tests for `VMConfig` isolation schema pass |
| AC-10 | Guest runs WORKSPACE-GUARD `e2e-guest.sh` (capability + policy-matrix) without host side effects |
| AC-11 | `make install-qemu` populates boot-dir binaries, firmware, and GPL NOTICE |
| AC-12 | `res/qemu-pins.yaml` version matches installed `qemu-system-* --version` |
| AC-13 | No workspace binary links `libqemu`; only subprocess invocation |
| AC-14 | `make test-vm-guard` passes on macOS (HVF) and Linux (KVM) |
| AC-15 | `tests/e2e/test_vm_qemu_full_ci.py` passes on macOS and Linux and verifies all 13 configured components on the guest disk |
| AC-16 | Host `/usr/bin/git` fingerprint unchanged after `make test-vm-guard` on both platforms |
| AC-17 | Persistent VM data survives stop, start, QEMU restart, and host reboot |
| AC-18 | `vm stop` performs guest ACPI shutdown and exits only after QEMU exits |
| AC-19 | `vm delete` preserves the overlay by default; `--purge` removes it |
| AC-20 | E2E cleanup never deletes a persistent VM |
| AC-21 | `vm rebuild` preserves the overlay by default and supports `--fresh` |
| AC-22 | `vm sync` applies merge, overwrite, skip, and exclude rules |
| AC-23 | Snapshot create, list, delete, export, and import pass E2E |
| AC-24 | Systemd autostart starts the VM after login and survives disable/enable |
| AC-25 | `files`, `mounts`, `env`, `provider`, `credentials`, `ssh`, and `web_ui` pass E2E |
| AC-26 | QEMU network none, bridge, proxy, and OpenVPN pass E2E; host mode is rejected |
| AC-27 | Every QEMU config field is implemented or rejected with a typed error |
| AC-28 | Windows and Android WSL or chroot bootstrap runs the Linux E2E gates |
| AC-29 | Docs, CLI help, status, and support matrix match tested behavior |
| AC-30 | Full persistent E2E suite passes on Linux KVM; macOS and WSL or chroot results are recorded |
| AC-31 | Native Windows, macOS, Android, and Linux package requirements are documented and linked |

Execution status for each criterion is tracked in §10.

---

## 8. Traceability

| Requirement | Spec section | Primary artifact |
|-------------|--------------|------------------|
| FR-1 | SPEC §1 Architecture | `workspace/cli/hypervisor/` |
| FR-2 | SPEC §5 PodmanBackend | `podman_backend.py`, `vm_build.py` |
| FR-3 | SPEC §6 QemuBackend | `qemu_backend.py` |
| FR-4 | SPEC §4 Schema | `workspace/types/vm.py` |
| FR-5 | SPEC §7 Accelerator | `qemu_backend.py` |
| FR-6 | SPEC §14 Platform Delivery | `vm_resolve.py`, WSL and chroot test matrix |
| FR-7 | SPEC §12 Guard | QEMU guard E2E, WORKSPACE-GUARD docs |
| FR-8 | SPEC §8 CLI parity | `vm_manager.py`, `vm_lifecycle.py`, `workspace/scripts/bin/vm` |
| FR-9 | SPEC §9 GPL separation | `qemu_backend.py`, `res/qemu-pins.yaml`, boot-dir NOTICE |
| FR-10 | SPEC §10 Bootstrap | `bootstrap_qemu.sh`, `bootstrap-components.yaml` |
| FR-11 | SPEC §11 Firmware/images | `.vms/_base/`, seed builder, EDK2 bundle |
| FR-12 | SPEC §6.5, §6.8 | `qemu_state.py`, `qemu_lifecycle.py` |
| FR-13 | SPEC §6.10 | `qemu_snapshots.py` |
| FR-14 | SPEC §6.11 | `qemu_lifecycle.py`, systemd unit templates |
| FR-15 | SPEC §6.12 | `qemu_guest_config.py`, `workspace/types/vm.py` |
| FR-16 | SPEC §6.12 | `qemu_network.py`, `qemu_argv.py` |

---

## 9. Open-Source Engine Rationale (Summary)

QEMU is the selected engine for the hardware-VM path because it is the only
mature, actively maintained, GPL-2.0-licensed engine with **TCG software
emulation on every host** plus native accelerators (KVM, HVF, WHPX). Alternatives
evaluated:

| Engine | License | Cross-platform VM? | v1 role |
|--------|---------|-------------------|---------|
| **QEMU** | GPL-2.0 | Yes (TCG + accel) | **Selected** |
| crosvm | BSD-3 | Needs host hypervisor | Future fast path |
| Firecracker | Apache-2.0 | Linux KVM only | Production microVMs later |
| Cloud Hypervisor | Apache-2.0 | KVM/MSHV only | Not selected |
| Rootless Podman | Apache-2.0 | Container, not VM | Retained default backend |

Full comparison table: [SPEC-VM-HYPERVISOR §15](../specifications/SPEC-VM-HYPERVISOR.md).

---

## 10. Implementation Status

Status as of 2026-10-23.

| Item | Status | Evidence |
|------|--------|----------|
| AC-1 REQ/SPEC committed, cross-linked | Implemented | This document pair |
| AC-2 `isolation` block in `vm-template.yaml`, default `podman` | Implemented | `workspace/config/vm-template.yaml` |
| AC-3 Podman `vm create` unchanged | Not verified this cycle | Podman regression pending |
| AC-4 QEMU guest boots from `vm-poc-qemu.yaml` | Implemented | Linux KVM and earlier macOS HVF |
| AC-5 SSH to forwarded port, Linux guest kernel | Implemented | QEMU E2E |
| AC-6 Host `/` unmodified by guest | Implemented | QEMU and guard host fingerprint checks |
| AC-7 `tests/e2e/test_vm_qemu_poc.py` | Implemented | Linux KVM pass 2026-10-22 |
| AC-8 `tests/e2e/test_vm_security.py` Podman tests | Not verified this cycle | Podman host run pending |
| AC-9 `VMConfig` isolation schema unit tests | Implemented | Unit suite |
| AC-10 Guest runs guard `e2e-guest.sh` without host side effects | Implemented | Linux KVM guard E2E pass 2026-10-22 |
| AC-11 `make install-qemu` boot bundle | Not verified | Fresh-host run pending |
| AC-12 `res/qemu-pins.yaml` matches installed version | Implemented | Pins and guard unit test |
| AC-13 No `libqemu` linkage | Implemented | Subprocess-only invocation |
| AC-14 `make test-vm-guard` on macOS (HVF) and Linux (KVM) | Partial | Linux pass; macOS pending |
| AC-15 `tests/e2e/test_vm_qemu_full_ci.py` (13 components) | Implemented | Linux full-ci pass |
| AC-16 Host `/usr/bin/git` fingerprint unchanged after guard E2E | Partial | Linux pass; macOS pending |
| AC-17 Persistent data survives restart | Implemented | State and overlay retained |
| AC-18 ACPI shutdown | Implemented | QMP powerdown, then SIGTERM/SIGKILL |
| AC-19 Delete preserve and purge | Implemented | Archive by default; purge removes artifacts |
| AC-20 Cleanup protects persistent VMs | Implemented | Cleanup skips persistent state |
| AC-21 QEMU rebuild | Implemented | Preserve or fresh overlay |
| AC-22 QEMU sync | Implemented | Merge, overwrite, skip, excludes |
| AC-23 Snapshot, export, import | Implemented | Manifest and integrity checks |
| AC-24 Systemd autostart | Implemented | `vm autostart enable|disable` |
| AC-25 Day-2 config parity | Partial | files, mounts, env, provider, credentials, SSH, web UI implemented |
| AC-26 Network parity | Partial | none, bridge policies, and openvpn container implemented; netns and whitelist rejected; runtime bridge/OpenVPN E2E pending |
| AC-27 Typed field rejection | Implemented | Unsafe fields fail with typed errors |
| AC-28 Windows and Android WSL or chroot bootstrap | Not implemented | Requirement added |
| AC-29 Documentation truth | Implemented | Docs match current behavior |
| AC-30 Full persistent E2E suite | Partial | Six QEMU E2E suites pass; bridge/OpenVPN runtime E2E pending |
| AC-31 Native package requirements | Implemented | REQ-NATIVE-VM-PACKAGES added |

Release gate: AC-14 and AC-16 remain authoritative for guard behavior. The
persistent product gate adds AC-17 through AC-30. Until they pass, documentation
SHALL describe QEMU as a supported create and test backend, not as a complete
persistent production VM.
