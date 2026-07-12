# VM Hypervisor Extension - Enterprise Requirements Specification

**Document ID:** WS-REQ-VM-HYPERVISOR-v1.0
**Status:** Draft
**Date:** 2026-07-11
**Classification:** Internal - Enterprise
**Specification:** [SPEC-VM-HYPERVISOR](SPEC-VM-HYPERVISOR.md)
**Tracking:** [TRACK-VM-HYPERVISOR](TRACK-VM-HYPERVISOR.md) (execution status and remaining tasks)
**Authors:** Workspace Engineering
**References:**
- [SPEC-VM-HYPERVISOR](SPEC-VM-HYPERVISOR.md) (Technical Specification)
- [REQ-BOOT-LAYOUT](REQ-BOOT-LAYOUT.md) (Platform boot directory resolution)
- [SPEC-BOOT-LAYOUT](SPEC-BOOT-LAYOUT.md) (Boot layout implementation)
- [REQ-OPENVPN](REQ-OPENVPN.md) (VM network modes - Podman backend)
- [REQ-ANDROID-WORKSPACE](REQ-ANDROID-WORKSPACE.md) (Android client - QEMU TCG bundle, Phase 2)
- [workspace/config/vm-template.yaml](../workspace/config/vm-template.yaml) (VM config reference)
- [projects/WORKSPACE-GUARD/docs/requirements/REQ-SANDBOX.md](../projects/WORKSPACE-GUARD/docs/requirements/REQ-SANDBOX.md) (Guard install / cap E2E authority)
- [AGENTS.md](../AGENTS.md) (Universal Agent Rules)

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
 auto-selection and TCG fallback

**In scope (v1 POC):**

- REQ/SPEC documentation
- `isolation.backend` schema extension in `workspace/types/vm.py`
- `workspace/cli/hypervisor/` module with `IsolationBackend` protocol
- `QemuBackend` POC on Linux and macOS hosts
- `PodmanBackend` thin wrapper (no behavioral change)
- POC config `workspace/config/vm-poc-qemu.yaml`
- E2E test: QEMU guest boots, SSH reachable, `uname -a` shows Linux kernel
- Authoritative WORKSPACE-GUARD capability + policy-matrix E2E inside QEMU guests
  (`make test-vm-guard`, `scripts/qemu/e2e-guest.sh`); Podman Tier 3 remains dev-only

**Out of scope (v1):**

- iOS host support
- Replacing or demoting rootless Podman for everyday agent development
- Windows WHPX bundle and Android client integration (Phase 2 - documented in SPEC)
- `vm rebuild` for QEMU backend (deferred)
- Traefik / web UI parity for QEMU guests (partial in POC - SSH shell only)

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
| **TCG** | QEMU Tiny Code Generator - software CPU emulation, universal fallback |
| **Accelerator** | Host-specific QEMU accel: `kvm` (Linux), `hvf` (macOS), `whpx` (Windows) |
| **Boot directory** | `.boot-linux` or `.boot-macos` - pinned tool binaries per REQ-BOOT-LAYOUT |
| **Base image** | Shared Ubuntu cloud image under `.vms/_base/` |
| **Overlay disk** | Per-VM QCOW2 overlay at `.vms/<uuid>/disk.qcow2` |
| **Cloud-init seed** | FAT/ISO seed image injecting SSH keys and first-boot provisioning |
| **Release gate** | WORKSPACE-GUARD cap/kernel E2E required inside QEMU; Darwin Podman is not sufficient |
| **Aggregation** | GPL applies to QEMU binaries distributed with the workspace; workspace Python code invokes QEMU as a separate process and does not link `libqemu` |
| **Pins manifest** | `res/qemu-pins.yaml` - pinned upstream version, checksums, and source URLs per platform |
| **Firmware bundle** | EDK2/OVMF blobs required for `virt`/`q35` machines; separate license from QEMU |

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

**FR-1.3** `make vm list`, `start`, `stop`, `delete`, `shell`, and `exec` SHALL
be backend-aware. POC MAY implement partial parity (see SPEC §8).

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

**FR-3.4 (REQ-VMH-009)** Host bind mounts into QEMU guests SHALL default to
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

**FR-4.2** `provider`, `credentials`, `ssh`, `files`, `sync`, `env`, and
`resources` fields SHALL remain in the shared schema. Backend-specific
interpretation of `security` and `network` is documented in SPEC §4.

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

**FR-5.3** QEMU binary resolution order SHALL be:
`<boot-dir>/bin/qemu-system-<arch>` → `PATH` → fail with bootstrap instructions.

### FR-6: Platform Support

**FR-6.1 (REQ-VMH-006)** QEMU POC SHALL support Linux and macOS developer hosts.

**FR-6.2** Windows WHPX and the Android client (per
[REQ-ANDROID-WORKSPACE](REQ-ANDROID-WORKSPACE.md)) SHALL be documented as Phase 2
in SPEC; not required for POC acceptance.

**FR-6.3 (REQ-VMH-010)** iOS SHALL be explicitly out of scope for v1.

**FR-6.4** `isolation.qemu.guest_arch` SHALL support `aarch64` and `x86_64`. POC
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
wait for SSH health, and print connection details.

**FR-8.2** `vm stop <id>` SHALL send ACPI shutdown or SIGTERM to QEMU process.

**FR-8.3** `vm delete <id>` SHALL terminate QEMU and remove `.vms/<id>/` artifacts
(overlay disk; base image in `_base/` is retained).

**FR-8.4** `vm shell <id>` for QEMU SHALL connect via SSH to forwarded localhost port.

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

**FR-9.6** Android packaging (Phase 2) SHALL use the same rule: JNI launches a repackaged
upstream QEMU binary; workspace Kotlin/Java code does not link QEMU as a library.

### FR-10: Bootstrap and version pinning

**FR-10.1 (REQ-VMH-012)** QEMU SHALL be a first-class bootstrap component
(`bootstrap-components.yaml` entry `qemu`) installed by `make install-qemu` /
`workspace/scripts/bootstrap/bootstrap_qemu.sh`.

**FR-10.2** Bootstrap SHALL install into the platform boot directory per
[REQ-BOOT-LAYOUT](REQ-BOOT-LAYOUT.md):

| Artifact | Linux path | macOS path |
|----------|------------|------------|
| `qemu-system-aarch64` | `.boot-linux/bin/` | `.boot-macos/bin/` |
| `qemu-system-x86_64` | `.boot-linux/bin/` | `.boot-macos/bin/` |
| `qemu-img` | `.boot-linux/bin/` | `.boot-macos/bin/` |
| EDK2 `QEMU_EFI.fd` (aarch64) | `.boot-linux/share/qemu/firmware/` | `.boot-macos/share/qemu/firmware/` |
| OVMF (x86_64, optional POC) | same | same |
| GPL notice bundle | `.boot-*/share/qemu/LICENSE`, `NOTICE` | same |

**FR-10.3** `res/qemu-pins.yaml` SHALL record for each platform: `version`, `sha256`,
`download_url` (or package name), `source_url` (QEMU release tarball), and
`firmware_packages` (apt/brew package names).

**FR-10.4** Linux bootstrap SHALL prefer **symlinks to distro packages** when versions
match the pin file. macOS SHALL symlink from Homebrew. Pinned tarball fallback is
allowed when distro version drifts.

**FR-10.5** POC MAY warn-and-fallback to `PATH` on developer hosts when boot-dir
binaries are absent. CI and release gates SHALL require boot-dir resolution (no silent
PATH fallback).

**FR-10.6** `config/system-deps.yaml` SHALL list host tools required by QEMU backend
that are not QEMU itself: `cloud-image-utils` (`cloud-localds`), and on Linux
`qemu-utils` when not fully bootstrapped.

### FR-11: Guest boot assets

**FR-11.1** AArch64 guests using `-machine virt` SHALL boot with EDK2 firmware from
the firmware bundle (`-bios` or pflash drives per SPEC).

**FR-11.2** Ubuntu base images SHALL be downloaded to `.vms/_base/` with SHA256
verification against `res/qemu-pins.yaml` (or a dedicated `res/vm-images.yaml` manifest).

**FR-11.3** Cloud-init seeds SHALL be built with `cloud-localds` (preferred) or
`mkisofs`/`genisoimage`; seed format SHALL be `nocloud` on a virtio block device.

**FR-11.4** Linux hosts using KVM SHALL document `/dev/kvm` group membership as a
prerequisite; macOS HVF requires no extra entitlement for `qemu-system-*`.

---

## 5. Non-Functional Requirements

**NFR-1** No breaking change to existing Podman-only workflows. Default backend
is `podman`; all current tests and configs pass without edits.

**NFR-2** No silent fallbacks for missing QEMU binary, base image, or failed
accelerator probe - surface explicit errors with bootstrap hints.

**NFR-3** No `dict[str, object]` in new Python code; use typed models per AGENTS.md.

**NFR-4** Shell scripts SHALL use `#!/bin/bash`, `set -euo pipefail`, and
`source ... || exit 1`.

**NFR-5** All new source files (non-markdown) SHALL remain under 512 lines.

**NFR-6** QEMU POC E2E test SHALL skip gracefully when QEMU binary or KVM/HVF is
unavailable, with a clear skip reason - not a false pass.

**NFR-7** Base Ubuntu image download SHALL be cached under `.vms/_base/` and
SHALL NOT be re-downloaded on every `vm create`.

**NFR-8** Guest SSH health wait SHALL reuse the existing `_wait_healthy` timeout
pattern from `vm_core.py` (adapted for SSH probe).

**NFR-9** Hypervisor Python modules SHALL stay below the 512-line file limit by splitting
`qemu_argv.py`, `qemu_images.py`, and `qemu_spawn.py` rather than growing a monolith.

**NFR-10** `qemu_backend.py` SHALL contain no GPL-licensed code; only MIT/Apache-compatible
workspace code that constructs argv and manages subprocess lifecycle.

---

## 6. Backend Selection Guide

| Use case | Backend |
|----------|---------|
| Daily agent dev, opencode web UI, fast iteration | **podman** |
| OpenVPN container / netns modes | **podman** |
| WORKSPACE-GUARD `setcap` / `chattr` install test | **qemu** |
| macOS / Windows host - agent must not touch host kernel | **qemu** |
| Android client app (Phase 2) | **qemu** (TCG bundle) |
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
| AC-15 | `tests/e2e/test_vm_qemu_full_ci.py` passes on macOS and Linux (13 components, guest disk) |
| AC-16 | Host `/usr/bin/git` fingerprint unchanged after `make test-vm-guard` on both platforms |

Execution status: [TRACK-VM-HYPERVISOR](TRACK-VM-HYPERVISOR.md).

---

## 8. Traceability

| Requirement | Spec section | Primary artifact |
|-------------|--------------|------------------|
| FR-1 | SPEC §1 Architecture | `workspace/cli/hypervisor/` |
| FR-2 | SPEC §5 PodmanBackend | `podman_backend.py`, `vm_build.py` |
| FR-3 | SPEC §6 QemuBackend | `qemu_backend.py` |
| FR-4 | SPEC §4 Schema | `workspace/types/vm.py` |
| FR-5 | SPEC §7 Accelerator | `qemu_backend.py` |
| FR-6 | SPEC §9 Phase 2 | Appendix |
| FR-7 | SPEC §10 Guard | `test_vm_qemu_poc.py`, WORKSPACE-GUARD docs |
| FR-8 | SPEC §8 CLI parity | `vm_manager.py`, `workspace/scripts/bin/vm` |
| FR-9 | SPEC §9 GPL separation | `qemu_backend.py`, `res/qemu-pins.yaml`, boot-dir NOTICE |
| FR-10 | SPEC §10 Bootstrap | `bootstrap_qemu.sh`, `bootstrap-components.yaml` |
| FR-11 | SPEC §11 Firmware/images | `.vms/_base/`, `cloud-localds`, EDK2 bundle |

---

## 9. Open-Source Engine Rationale (Summary)

QEMU is the selected engine for the hardware-VM path because it is the only
mature, actively maintained, GPL-2.0-licensed engine with **TCG software
fallback on every host** plus native accelerators (KVM, HVF, WHPX). Alternatives
evaluated:

| Engine | License | Cross-platform VM? | v1 role |
|--------|---------|-------------------|---------|
| **QEMU** | GPL-2.0 | Yes (TCG + accel) | **Selected** |
| crosvm | BSD-3 | Needs host hypervisor | Future fast path |
| Firecracker | Apache-2.0 | Linux KVM only | Production microVMs later |
| Cloud Hypervisor | Apache-2.0 | KVM/MSHV only | Not POC |
| Rootless Podman | Apache-2.0 | Container, not VM | Retained default backend |

Full comparison table: [SPEC-VM-HYPERVISOR §15](SPEC-VM-HYPERVISOR.md).