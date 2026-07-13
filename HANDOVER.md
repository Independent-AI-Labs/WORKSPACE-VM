# WORKSPACE-VM Handover (Superseded)

**Date:** 2026-07-13
**Status:** SUPERSEDED

This document previously described an early macOS Traefik / `launch-mac.sh` integration path. That code has been replaced by the unified `make vm` Python CLI, dual Podman/QEMU hypervisor backends, and platform boot directories (`.boot-linux` / `.boot-macos`).

## Use these instead

| Topic | Document |
| :--- | :--- |
| Onboarding | [`README.md`](README.md) |
| Doc index | [`docs/README.md`](docs/README.md) |
| VM / QEMU | [`docs/SPEC-VM-HYPERVISOR.md`](docs/SPEC-VM-HYPERVISOR.md), [`docs/TRACK-VM-HYPERVISOR.md`](docs/TRACK-VM-HYPERVISOR.md) |
| OpenVPN | [`docs/SPEC-OPENVPN.md`](docs/SPEC-OPENVPN.md) |
| LLM / GPU setup | [`docs/SPEC-LLAMA-SETUP-TUI.md`](docs/SPEC-LLAMA-SETUP-TUI.md) |

## Historical detail

The original Traefik-in-container handover (2025-06-13) is preserved in git history at commit `7b88dc2b` and earlier. Do not follow paths referenced there (`launch-mac.sh`, `install-mac.sh`, `tests/host_vm/mac/`); they no longer exist on `main`.