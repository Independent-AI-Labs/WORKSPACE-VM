# Native VM End-User Packages - Requirements Specification

**Document ID:** WS-REQ-NATIVE-VM-PACKAGES-v1.0
**Status:** Draft
**Date:** 2026-10-23
**Classification:** Internal - Enterprise
**Specification:** Pending
**References:**
- [REQ-VM-HYPERVISOR](REQ-VM-HYPERVISOR.md)
- [REQ-ANDROID-WORKSPACE](REQ-ANDROID-WORKSPACE.md)
- [SPEC-VM-HYPERVISOR](../specifications/SPEC-VM-HYPERVISOR.md)
- [PERSISTENT-QEMU-VM guide](../guides/PERSISTENT-QEMU-VM.md)

---

## 1. Scope

This document tracks native end-user packages for the QEMU VM backend.

Packages are separate delivery workstreams:

- Native Windows package with WHPX
- Native macOS package with HVF
- Native Android package with bundled QEMU TCG
- Native Linux package or packages

The shared QEMU backend, persistent VM state, CLI contract, and E2E matrix are
defined in WORKSPACE-VM. Native packages SHALL consume that contract.

Windows and Android developers are supported before native packages ship through
the rootless bootstrap path on a local Debian or Ubuntu environment under WSL or
chroot. That path is not a native package and SHALL NOT be described as one.

---

## 2. Shared Requirements

**NP-1** Native packages SHALL use the same persistent VM state model as the
rootless QEMU backend: QCOW2 overlay, `state.yaml`, snapshots, export, and import.

**NP-2** Native packages SHALL support create, start, stop, rebuild, sync,
snapshot, export, import, delete, shell, exec, logs, status, and autostart.

**NP-3** Native packages SHALL enforce the same accelerator selection rules:
WHPX on Windows, HVF on macOS, KVM on Linux, TCG when required.

**NP-4** Native packages SHALL ship QEMU as a separate executable or bundled
binary. They SHALL NOT link `libqemu` into application code.

**NP-5** Native packages SHALL ship GPL notices, license text, version pins, and
source URLs for QEMU and firmware.

**NP-6** Native packages SHALL preserve VM data across upgrade and uninstall
unless the user explicitly purges it.

**NP-7** Native packages SHALL NOT claim support until their platform E2E gate
passes.

**NP-8** Native packages SHALL use the same config schema as WORKSPACE-VM. Fields
that cannot be implemented SHALL fail with a typed validation error.

**NP-9** Native packages SHALL support snapshot, export, and import for backup.

**NP-10** Native packages SHALL support systemd or platform-equivalent autostart.
Windows uses a service or startup task. macOS uses launchd. Android uses a
foreground service. Linux uses systemd.

---

## 3. Native Windows

**NW-1** Windows SHALL use WHPX when available and TCG otherwise.

**NW-2** Windows SHALL provide a signed installer or MSIX package.

**NW-3** Windows SHALL provide a service or startup task for autostart.

**NW-4** Windows SHALL support WSL2 use for development, but the WSL path is not
the native package.

**NW-5** Windows SHALL have E2E coverage for install, create, persistence,
snapshot, export, import, upgrade, uninstall, and autostart.

---

## 4. Native macOS

**NM-1** macOS SHALL use HVF when available and TCG otherwise.

**NM-2** macOS SHALL provide a signed and notarized app or package.

**NM-3** macOS SHALL provide a launchd agent for autostart.

**NM-4** macOS SHALL have E2E coverage for install, create, persistence, snapshot,
export, import, upgrade, uninstall, and autostart.

**NM-5** macOS HVF validation SHALL be recorded separately from Linux KVM and
from the existing historical HVF result.

---

## 5. Native Android

**NA-1** Native Android SHALL follow
[REQ-ANDROID-WORKSPACE](REQ-ANDROID-WORKSPACE.md).

**NA-2** Native Android SHALL package QEMU as W^X-safe `jniLibs` binaries.

**NA-3** Native Android SHALL use a foreground service for VM lifecycle and
autostart.

**NA-4** Native Android SHALL have E2E coverage for install, create, persistence,
snapshot, export, import, upgrade, uninstall, and autostart.

**NA-5** The WSL or chroot developer path is not an Android package and SHALL NOT
be used as packaging evidence.

---

## 6. Native Linux

**NL-1** Native Linux SHALL use KVM when available and TCG otherwise.

**NL-2** Native Linux SHALL provide a package format selected by release
engineering, such as deb, rpm, or AppImage.

**NL-3** Native Linux SHALL use a systemd unit for autostart.

**NL-4** Native Linux SHALL have E2E coverage for install, create, persistence,
snapshot, export, import, upgrade, uninstall, and autostart.

---

## 7. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| NPC-1 | Shared package contract is documented and linked from the VM requirement |
| NPC-2 | Each platform package consumes the shared persistent state model |
| NPC-3 | Each platform package preserves data across upgrade and uninstall |
| NPC-4 | Each platform package supports snapshot, export, and import |
| NPC-5 | Each platform package supports autostart with platform semantics |
| NPC-6 | Each platform package passes its own E2E gate |
| NPC-7 | GPL notices and source offers are present in every package |
| NPC-8 | WSL or chroot developer support is documented separately from native packages |
