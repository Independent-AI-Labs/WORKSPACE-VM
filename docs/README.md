# AMI-Agents V3 - Documentation

**Date:** 2026-07-17
**Status:** ACTIVE

Active documentation for the AMI-Agents V3 workspace. Pre-V3 docs have been
removed from the repo and are preserved in git history.

Documents are organized by type: requirement contracts (REQ-*), implementation
specifications (SPEC-*), historical plans and executed migrations
(proposals/), and dated audit reports (audits/). Documents with
**Status: Draft** describe features that are not yet implemented; their
Implementation Status sections mark every component as not implemented.

Start here for onboarding: [`../README.md`](../README.md)

---

## Tree

### requirements/ - requirement contracts (REQ-*)

| Document | Scope |
|----------|-------|
| [`requirements/REQ-AGENT-POLICY.md`](requirements/REQ-AGENT-POLICY.md) | Agent policy engine: YAML DSL, profiles, audit trail (Draft) |
| [`requirements/REQ-A2A.md`](requirements/REQ-A2A.md) | A2A remote-agent client integration, regulatory controls (Draft) |
| [`requirements/REQ-ANDROID-WORKSPACE.md`](requirements/REQ-ANDROID-WORKSPACE.md) | Android app running bundled Ubuntu ARM64 VM (Draft) |
| [`requirements/REQ-BOOT-LAYOUT.md`](requirements/REQ-BOOT-LAYOUT.md) | Platform boot directory (`.boot-linux` / `.boot-macos`) resolution |
| [`requirements/REQ-LLAMA-SETUP-TUI.md`](requirements/REQ-LLAMA-SETUP-TUI.md) | `make llama-setup` unified llama/GPU setup wizard |
| [`requirements/REQ-LLAMAFILE-MINICPM5-1B.md`](requirements/REQ-LLAMAFILE-MINICPM5-1B.md) | MiniCPM5-1B llamafile bundles (server + chat) |
| [`requirements/REQ-OPENVPN.md`](requirements/REQ-OPENVPN.md) | Host and VM OpenVPN client automation |
| [`requirements/REQ-VM-HYPERVISOR.md`](requirements/REQ-VM-HYPERVISOR.md) | `make vm` dual isolation backends (Podman + QEMU) |

### specifications/ - implementation specs (SPEC-*)

| Document | Scope |
|----------|-------|
| [`specifications/SPEC-AGENT-POLICY.md`](specifications/SPEC-AGENT-POLICY.md) | Policy engine implementation: bash + yq pipeline, static plugin (Draft) |
| [`specifications/SPEC-A2A.md`](specifications/SPEC-A2A.md) | A2A client implementation design (Draft) |
| [`specifications/SPEC-ANDROID-WORKSPACE.md`](specifications/SPEC-ANDROID-WORKSPACE.md) | Android VM app implementation design (Draft) |
| [`specifications/SPEC-BOOT-LAYOUT.md`](specifications/SPEC-BOOT-LAYOUT.md) | Boot layout implementation in `projects/CI/lib/ci.sh` |
| [`specifications/SPEC-LLAMA-SETUP-TUI.md`](specifications/SPEC-LLAMA-SETUP-TUI.md) | Setup wizard phases, profiles, prereq scripts |
| [`specifications/SPEC-LLAMAFILE-MINICPM5-1B.md`](specifications/SPEC-LLAMAFILE-MINICPM5-1B.md) | llamafile bundle format and CPU cosmocc build |
| [`specifications/SPEC-OPENVPN.md`](specifications/SPEC-OPENVPN.md) | `make vpn-*` automation: bootstrap, host service, VM pipeline |
| [`specifications/SPEC-VM-HYPERVISOR.md`](specifications/SPEC-VM-HYPERVISOR.md) | Hypervisor architecture, QEMU backend, guard E2E gate |

### proposals/ - plans and executed migrations

| Document | Scope |
|----------|-------|
| [`proposals/MIGRATION-PLAN.md`](proposals/MIGRATION-PLAN.md) | V3 migration master plan (Active; see banner for current phase) |
| [`proposals/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md`](proposals/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md) | CLI components move to AMI-DATAOPS (Executed 2026-06-01) |

### audits/ - dated audit reports

| Document | Scope |
|----------|-------|
| [`audits/GAP-ANALYSIS-A2A.md`](audits/GAP-ANALYSIS-A2A.md) | A2A codebase gap analysis against closed PR #10452 (Final, 2026-06-01) |

### benchmarking/

Generated report data (for example `llamafile-transcript-classifier/`);
not hand-written documentation. See
[`../benchmarks/llamafile/transcript_classifier/README.md`](../benchmarks/llamafile/transcript_classifier/README.md)
for the benchmark itself.

---

## Reading order for newcomers

1. [`../README.md`](../README.md) - workspace overview and make targets.
2. [`requirements/REQ-BOOT-LAYOUT.md`](requirements/REQ-BOOT-LAYOUT.md) + [`specifications/SPEC-BOOT-LAYOUT.md`](specifications/SPEC-BOOT-LAYOUT.md) - the platform toolchain directory everything else builds on.
3. [`requirements/REQ-VM-HYPERVISOR.md`](requirements/REQ-VM-HYPERVISOR.md) + [`specifications/SPEC-VM-HYPERVISOR.md`](specifications/SPEC-VM-HYPERVISOR.md) - agent VM isolation backends and the authoritative guard E2E gate.
4. [`requirements/REQ-OPENVPN.md`](requirements/REQ-OPENVPN.md) + [`specifications/SPEC-OPENVPN.md`](specifications/SPEC-OPENVPN.md) - host/VM VPN automation.
5. [`requirements/REQ-LLAMA-SETUP-TUI.md`](requirements/REQ-LLAMA-SETUP-TUI.md) + [`specifications/SPEC-LLAMAFILE-MINICPM5-1B.md`](specifications/SPEC-LLAMAFILE-MINICPM5-1B.md) - local LLM inference stack.
6. Draft docs (`REQ-AGENT-POLICY`, `REQ-A2A`, `REQ-ANDROID-WORKSPACE` and their SPECs) - planned features.
7. [`proposals/MIGRATION-PLAN.md`](proposals/MIGRATION-PLAN.md) - historical V3 phase context.

## Archive

V2-era documentation has been removed from the repo and is preserved in git
history. Legacy Traefik/macOS handover notes: see
[`../HANDOVER.md`](../HANDOVER.md) (superseded; pointer only).
