# REQ-LLAMA-SETUP-TUI: Llama / Hardware Setup TUI

**Date:** 2026-07-17
**Status:** Active
**Type:** Requirements
**Specification:** [SPEC-LLAMA-SETUP-TUI](../specifications/SPEC-LLAMA-SETUP-TUI.md)

> Contract for the unified `make llama-setup` wizard that owns detection,
> prerequisites, builds, bundling, deployment, and diagnostics for the llama
> inference stack (llama.cpp flavors, llamafile bundles, Intel GPU / Vulkan).
> This document is the single source of truth for what the wizard MUST do;
> wizard mechanics live in the companion specification. Explicitly excluded:
> per-model bundle format details (owned by
> [REQ-LLAMAFILE-MINICPM5-1B](REQ-LLAMAFILE-MINICPM5-1B.md)).

---

**Cross-references:**
- [SPEC-LLAMA-SETUP-TUI](../specifications/SPEC-LLAMA-SETUP-TUI.md): companion specification
- [`workspace/config/llama-setup.yaml`](../../workspace/config/llama-setup.yaml): stack profile registry
- [`workspace/config/llama-setup-defaults.yaml`](../../workspace/config/llama-setup-defaults.yaml): CI defaults

---

## 1. Purpose & Scope

### 1.1 Purpose

Replace the scattered llama/GPU install paths (`make install` checkboxes,
`Makefile.llamaserver` / `Makefile.llamafile`, Ansible roles, duplicated Intel
install scripts) with one interactive wizard and one non-interactive CI entry.

### 1.2 Scope

**This document OWNS the requirements for:**
- The `make llama-setup` (interactive) and `make llama-setup-ci` (defaults) entry points
- Hardware detection, prerequisite install, stack builds, model bundling, service deploy
- The stack profile registry and prereq script contract

**This document DOES NOT:**
- Define the llamafile bundle format (see REQ-LLAMAFILE-MINICPM5-1B)
- Own benchmark tooling (see `benchmarks/llamafile/`)

### 1.3 Terminology

| Term | Definition |
|------|------------|
| Stack profile | Named build+deploy combination in `llama-setup.yaml` (e.g. `llamafile_vulkan_server`) |
| Flavor | `llamaserver@<flavor>` systemd template instance (`vulkan`, `sycl`, `cpu`) |

## 2. Functional Requirements

### FR-1: Entry points

| ID | Requirement |
|----|-------------|
| FR-1.1 | `make llama-setup` MUST launch the interactive wizard. |
| FR-1.2 | `make llama-setup-ci` MUST run non-interactively from `llama-setup-defaults.yaml`. |
| FR-1.3 | Llama and GPU components MUST NOT appear in `make install`; the TUI is the only install path. |

### FR-2: Wizard phases

| ID | Requirement |
|----|-------------|
| FR-2.1 | The wizard MUST detect hardware (`render`/`video` groups, `xpu-smi`, `vulkaninfo`, Vulkan GPU probe, existing builds/services) without sudo. |
| FR-2.2 | Prerequisite installation (Intel drivers, Vulkan dev, oneAPI) MUST go through `scripts/setup/install-intel-gpu.sh` flags and MUST be the only sudo phase. |
| FR-2.3 | The wizard MUST build the selected stack profiles without sudo. |
| FR-2.4 | The wizard MUST produce `.llamafile` bundles under `models/<name>/`. |
| FR-2.5 | Deployment MUST go through Ansible as `llamafile-<model>` or `llamaserver@<flavor>` user units, without sudo. |

### FR-3: Profiles and prereqs

| ID | Requirement |
|----|-------------|
| FR-3.1 | The registry MUST define at minimum: `llamafile_vulkan_server`, `llama_cpp_vulkan`, `llama_cpp_sycl`, `llama_cpp_cpu`, `llamafile_cpu_chat`. |
| FR-3.2 | Prereq scripts MUST cover `intel_drivers`, `intel_monitoring` (`--monitoring-only`), `vulkan_dev`, and `oneapi`. |
| FR-3.3 | The wizard MUST delegate to existing Make targets so scripted use can bypass the TUI (`Makefile.llamafile`, `Makefile.llamaserver`). |

## 3. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1.1 | Only the prereq phase MAY require sudo; all other phases MUST run unprivileged. |
| NFR-1.2 | UI and logic MUST be split, following `bootstrap_installer.py` patterns. |
| NFR-1.3 | A single `vulkaninfo` parse per service start MUST be cached (`--cache-file`). |

## 4. Constraints

| ID | Constraint | Source |
|----|------------|--------|
| C-1 | After Intel driver install, `newgrp render` or re-login is required before GPU probes succeed | kernel group semantics |

## 5. Assumptions

| ID | Assumption |
|----|------------|
| A-1 | Target hosts are Linux with Intel GPUs for Vulkan/SYCL profiles. |

## 6. Open Questions

None.

## 7. Verification Matrix

| # | Test | Maps to |
|---|------|---------|
| V1 | `make llama-setup-ci` completes with defaults YAML | FR-1.2 |
| V2 | Built `llamafile-<model>` user unit serves on its port | FR-2.5 |
| V3 | `make install` shows no llama/GPU components | FR-1.3 |

## 8. Implementation Status

| Item | Status | Evidence |
|------|--------|----------|
| FR-1 Entry points | Implemented | `Makefile` (`llama-setup`, `llama-setup-ci`) |
| FR-2 Wizard phases | Implemented | `workspace/scripts/llama_setup_installer.py` and siblings |
| FR-3 Profiles + prereq scripts | Implemented | `workspace/config/llama-setup.yaml`, `scripts/setup/install-intel-gpu.sh`, `scripts/setup/install-vulkan-dev.sh` |
