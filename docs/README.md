# AMI-Agents V3 - Documentation

**Date:** 2026-07-13
**Status:** ACTIVE

Active documentation for the AMI-Agents V3 workspace. Pre-V3 docs have been removed from the repo and are preserved in git history.

Start here for onboarding: [`../README.md`](../README.md)

---

## Migration

- [`MIGRATION-PLAN.md`](MIGRATION-PLAN.md) - V3 migration master plan (active; see banner for current phase)
- [`MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md`](MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md) - CLI components move to AMI-DATAOPS (executed)

## VM / Hypervisor

- [`REQ-VM-HYPERVISOR.md`](REQ-VM-HYPERVISOR.md) - Requirements for Podman + QEMU backends
- [`SPEC-VM-HYPERVISOR.md`](SPEC-VM-HYPERVISOR.md) - Architecture and implementation spec
- [`TRACK-VM-HYPERVISOR.md`](TRACK-VM-HYPERVISOR.md) - Operational tracking and verification checklist
- [`REQ-ANDROID-WORKSPACE.md`](REQ-ANDROID-WORKSPACE.md) - Android host constraints

## OpenVPN

- [`REQ-OPENVPN.md`](REQ-OPENVPN.md) - Host and VM VPN requirements
- [`SPEC-OPENVPN.md`](SPEC-OPENVPN.md) - `make vpn-*` automation spec

## Llama / Inference

- [`SPEC-LLAMA-SETUP-TUI.md`](SPEC-LLAMA-SETUP-TUI.md) - `make llama-setup` wizard (recommended entrypoint)
- [`SPEC-LLAMAFILE-MINICPM5-1B.md`](SPEC-LLAMAFILE-MINICPM5-1B.md) - llamafile bundle format and build procedure

## Boot Layout

- [`REQ-BOOT-LAYOUT.md`](REQ-BOOT-LAYOUT.md) - Platform boot directory requirements
- [`SPEC-BOOT-LAYOUT.md`](SPEC-BOOT-LAYOUT.md) - `.boot-linux` / `.boot-macos` layout
- [`SPEC-VM-ROOT-REFACTOR.md`](SPEC-VM-ROOT-REFACTOR.md) - VM root refactor notes

## Agent Policy

- [`REQ-AGENT-POLICY.md`](REQ-AGENT-POLICY.md) - Agent policy requirements
- [`SPEC-AGENT-POLICY.md`](SPEC-AGENT-POLICY.md) - Agent policy specification

## A2A (Agent-to-Agent)

- [`GAP-ANALYSIS-A2A.md`](GAP-ANALYSIS-A2A.md) - A2A codebase gap analysis
- [`REQUIREMENTS-A2A.md`](REQUIREMENTS-A2A.md) - A2A enterprise requirements spec

## Benchmarks

- [`../benchmarks/llamafile/transcript_classifier/README.md`](../benchmarks/llamafile/transcript_classifier/README.md) - Rolling-window transcript classifier benchmark

Reports are written under `docs/benchmarking/llamafile-transcript-classifier/` (gitignored).

## Archive

V2-era documentation has been removed from the repo and is preserved in git history.

Legacy Traefik/macOS handover notes: see [`../HANDOVER.md`](../HANDOVER.md) (superseded; pointer only).