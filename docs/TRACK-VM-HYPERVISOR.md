# VM Hypervisor Extension - Implementation Tracking

**Document ID:** WS-TRACK-VM-HYPERVISOR-v1.0
**Status:** Active
**Date:** 2026-07-12
**Requirements:** [REQ-VM-HYPERVISOR](REQ-VM-HYPERVISOR.md)
**Specification:** [SPEC-VM-HYPERVISOR](SPEC-VM-HYPERVISOR.md)

Operational checklist for QEMU hypervisor POC sign-off. Normative acceptance
criteria live in REQ §7 and SPEC §13; this file tracks execution status and
remaining tasks only.

---

## 1. POC Acceptance Status

Maps to [SPEC §13](SPEC-VM-HYPERVISOR.md) and REQ AC-1 through AC-16.

| Step | Command / check | Expected | Status |
|------|-----------------|----------|--------|
| 1 | Read REQ + SPEC | Documents exist, cross-linked | Done |
| 2 | `cargo test` / `make test` (VM repo) | Unit tests pass including isolation schema | Done |
| 3 | `vm create workspace/config/vm-poc-qemu.yaml` | QEMU starts, UUID printed | Done (macOS HVF) |
| 4 | `ssh -p <port> workspace@127.0.0.1 uname -a` | Linux kernel string | Done (macOS HVF) |
| 5 | Verify host `/usr/bin/git` unchanged | No guard artifacts on host | Done (POC path) |
| 6 | `pytest tests/e2e/test_vm_qemu_poc.py` | Pass or skip with reason | Done (macOS, ~93s) |
| 7 | `pytest tests/e2e/test_vm_security.py` | Podman tests still pass | Not verified |
| 8 | `pytest tests/e2e/test_vm_qemu_full_ci.py` | 13 components on guest disk (macOS + Linux) | **TODO** |
| 9 | `make test-vm-guard` | WORKSPACE-GUARD e2e-guest.sh in QEMU; host git unchanged | **In progress** (manual e2e-guest PASS 2026-07-12; full pytest re-run pending) |

Step 9 is the authoritative release gate: capability install, policy-matrix live
vectors on real guest caps, and host `/usr/bin/git` fingerprint unchanged.
See SPEC §12.1 and REQ FR-7.

---

## 2. Implementation Progress

Maps to [SPEC §16](SPEC-VM-HYPERVISOR.md).

| # | Milestone | Status |
|---|-----------|--------|
| 1 | `REQ-VM-HYPERVISOR.md` + `SPEC-VM-HYPERVISOR.md` | Done |
| 2 | Extend `VMConfig` + `vm-template.yaml` with `isolation` block | Done |
| 3 | Add `workspace/cli/hypervisor/` package | Done |
| 4 | Refactor `vm_manager.create` to dispatch on backend | Done |
| 5 | Add `bootstrap_qemu.sh` + `.vms/_base/` image fetch | Done (SHA256 pinned, §3.1) |
| 6 | Add `vm-poc-qemu.yaml` + `test_vm_qemu_poc.py` | Done (macOS HVF passed) |
| 7 | Guest provision (`qemu_provision.py`) + virtio-9p RO mount | Done (cloud-init YAML + mount probe fixes) |
| 8 | `vm-full-ci-qemu.yaml` + `make test-vm-guard` + authoritative E2E suite | In progress (provision path fixed; pytest gate pending re-run, §3) |

---

## 3. Remaining Work

### 3.1 SHA256 image pins (REQ FR-11.2, AC-12)

**Artifact:** `res/qemu-pins.yaml`

**Status:** Done (2026-07-12, macOS host).

- `ubuntu_2404_arm64`: `cafa1a965b591b7c4184b484ffd8e625981a79d48f9b4ae8a4adf7b4c5ade927`
- `ubuntu_2404_x86_64`: `5fa5b05e5ec239858c4531485d6023b0896448c2df7c63b34f8dae6ea6051a44`
- CI guard: `tests/unit/cli/hypervisor/test_qemu_images.py::test_qemu_pins_no_pending_sha256`

### 3.2 Authoritative guard E2E (REQ FR-7, AC-10/14/16, §1 step 9)

**Artifacts:** `workspace/config/vm-guard-qemu.yaml`, `tests/e2e/test_vm_qemu_guard.py`,
`projects/WORKSPACE-GUARD/scripts/qemu/e2e-guest.sh`, `make test-vm-guard`.

**Tasks:**

1. **macOS (HVF):** `make clean-qemu-e2e && make test-vm-guard` (~30+ min).
   - Guest provisions `guard` profile (CI + WORKSPACE-GUARD rsync).
   - `e2e-guest.sh` runs `e2e-capability.sh` + `e2e-policy-matrix.sh` on guest `/usr/bin/git`.
   - `tests/e2e/qemu_host_isolation.py` confirms host git fingerprint unchanged.
2. **Linux (KVM):** repeat on a host with `/dev/kvm` (REQ FR-11.4).
3. On failure: inspect `.vms/<uuid>/provision.log`, guest `qemu.log`, SSH output from guard run.
4. Mark §1 step 9 **Done** only when both macOS and Linux pass.

### 3.3 Full-CI guest provision E2E (REQ AC-15, §1 step 8)

**Artifacts:** `workspace/config/vm-full-ci-qemu.yaml`, `tests/e2e/test_vm_qemu_full_ci.py`,
`make test-e2e-qemu-full`.

**Tasks:**

1. **macOS (HVF):** `make clean-qemu-e2e && pytest tests/e2e/test_vm_qemu_full_ci.py -v -m e2e --timeout 3600`
   (~45-90 min; `make install-ci` for 13 default components inside guest).
2. **Linux (KVM):** repeat.
3. Verify essential binaries on guest disk (`uv`, `python3`, `node`, `opencode` per test).
4. Mark §1 step 8 **Done** when both platforms pass.

### 3.4 Pre-release authoritative checklist

**Artifact:** `make test-authoritative` (= `test-e2e-qemu-full`).

**Tasks:**

1. After §3.2 and §3.3 pass individually, run `make test-authoritative` end-to-end
   (POC + full-ci + guard in one pytest invocation).
2. Confirm `tests/e2e/qemu_host_isolation.py` before/after host git checks in guard test.
3. Record pass date and host OS/accel in §1 status rows.

### 3.5 Linux KVM accelerator parity (REQ FR-5, SPEC §7, §11.4)

**Not validated on macOS**: HVF path only exercised so far.

**Tasks:**

1. On Linux host: confirm `resolve_accel` selects `kvm` when `/dev/kvm` present.
2. Run §1 steps 6, 8, 9 under KVM (not TCG fallback).
3. If `/dev/kvm` missing: verify `accel: auto` falls back to `tcg` with warning; explicit
   `accel: kvm` fails with `usermod -aG kvm` hint (SPEC §11.4).
4. Optional: add pytest marker or env `QEMU_EXPECT_ACCEL=kvm` to assert accel in `qemu.log`.

### 3.6 x86_64 guest architecture (REQ FR-6.4)

**Artifacts:** `res/qemu-pins.yaml#ubuntu_2404_x86_64`, SPEC §11.3 OVMF table.

**Tasks:**

1. Pin SHA256 for `ubuntu_2404_x86_64` (§3.1).
2. Add or reuse a POC config with `isolation.qemu.guest_arch: x86_64` on an x86_64 host.
3. Boot + SSH sanity check (`uname -m` -> `x86_64`).
4. Re-run guard E2E (§3.2) on x86_64 guest if release matrix requires it.

### 3.7 Podman regression (§1 step 7)

**Tasks:**

1. `pytest tests/e2e/test_vm_security.py -v -m e2e` on a host with Podman.
2. Confirm existing Podman `vm create` unchanged (REQ AC-3).

### 3.8 `make install-qemu` boot bundle (REQ AC-11)

**Tasks:**

1. Fresh host: `make install-qemu` populates `.boot-*/bin/qemu-system-*`, firmware, GPL NOTICE.
2. Confirm `res/qemu-pins.yaml#qemu.version` matches `qemu-system-aarch64 --version`.
3. Mark AC-11 satisfied in §1 when verified.

### 3.9 Phase 2 - explicitly deferred (not blocking POC)

See [SPEC §14](SPEC-VM-HYPERVISOR.md). Do not schedule for v1 sign-off:

- `vm rebuild` / `vm sync` for QEMU backend (SPEC §8)
- Traefik / opencode web UI in QEMU guests
- Windows WHPX bundle
- Android client TCG `.so` bundle