# SPEC-ANDROID-WORKSPACE: Android Workspace Client Implementation

**Date:** 2026-07-17
**Status:** Draft
**Type:** Specification
**Requirements:** [REQ-ANDROID-WORKSPACE](../requirements/REQ-ANDROID-WORKSPACE.md)

> Intended design for the Android app that runs a bundled Ubuntu ARM64 VM via
> QEMU TCG inside the app sandbox. Not implemented; no Android module exists
> in this repo. Key invariants: no root, W^X-safe `jniLibs` packaging, QEMU
> invoked as external process only (GPL-2.0 separation).

---

**Cross-references:**
- [REQ-ANDROID-WORKSPACE](../requirements/REQ-ANDROID-WORKSPACE.md): requirements contract
- [SPEC-VM-HYPERVISOR](SPEC-VM-HYPERVISOR.md): desktop QEMU backend whose argv builder is shared (Phase 2)

---

## 1. Overview

A single-activity Jetpack Compose app plus a foreground `VmService` that:

1. Extracts `qemu-system-aarch64`, `qemu-img`, and `virgl_test_server_android`
   from `jniLibs/` and launches them from the executable native library path.
2. Boots a QCOW2 overlay backed by a pristine Ubuntu cloud base image with a
   cloud-init NoCloud seed.
3. Starts VirGL before QEMU and renders the guest desktop through Termux:X11
   (primary) or a bundled VNC client (fallback).
4. Stages user playbook directories over VirtFS (9p) and runs
   `ansible-playbook` inside the guest over forwarded SSH.

## 2. Architectural Principles

### 2.1 Sandbox purity

All execution stays inside the app UID; no root, no Termux dependency, no
host setup. Networking is QEMU user-mode NAT only.

### 2.2 GPL separation

Android (Kotlin/Java) code launches the repackaged upstream QEMU binary as a
separate process. `LICENSE` and `NOTICE` with version and source URL ship in
the app; no `libqemu` linkage.

### 2.3 Shared QEMU argv builder

The Android launcher reuses the argv-construction patterns of the desktop
`workspace/cli/hypervisor/qemu_backend.py` (forced `-accel tcg`,
`-cpu max,pauth-impdef=on`, `virtio-gpu-gl-pci,virgl=on`).

## 3. System Diagram

```
AAB install -> extract assets -> app private storage
   |-- jniLibs .so binaries --> VmService -> VirGL server -> QEMU (TCG)
   |-- ubuntu-base.img -------> qcow2 overlay (vm-disk.qcow2)
   +-- seed.img (cloud-init) -> first boot: user, ssh, XFCE4, LightDM
UI: Dashboard | Console (desktop, logs, Run Ansible) | Settings
```

## 4. Key Decisions

| Decision | Rationale |
|----------|-----------|
| `jniLibs` `.so` repackaging | W^X: `filesDir` is `noexec`; extracted lib path is not |
| `useLegacyPackaging = true` | Uncompressed extraction keeps binaries executable |
| TCG only, `pauth-impdef=on` | KVM unavailable to unprivileged apps; pauth flag cuts boot time |
| Play asset delivery for base image | Keeps initial APK under size limit (~400 MB image) |
| Foreground service + watchdog | Prevents OS kill of QEMU; graceful ACPI shutdown on swipe-away |
| `EncryptedSharedPreferences` | Protects guest SSH credentials and vault passwords |

## 5. File Map

| File | Purpose | Key Changes |
|------|---------|-------------|
| Android app module (planned) | Compose UI + `VmService` | New repo/module |
| `workspace/cli/hypervisor/qemu_backend.py` | Shared argv builder | Extract reusable builder (Phase 2) |

## 6. Implementation Status

| Component | Status | Evidence |
|-----------|--------|----------|
| AAB packaging + asset delivery | Not implemented | No Android module |
| `VmService` lifecycle + watchdog | Not implemented | - |
| QEMU/VirGL `jniLibs` bundle | Not implemented | - |
| cloud-init seed generation | Not implemented | - |
| VirtFS + Ansible run bridge | Not implemented | - |
| Management UI | Not implemented | - |
