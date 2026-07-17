# REQ-LLAMAFILE-MINICPM5-1B: llamafile Bundles for MiniCPM5-1B

**Date:** 2026-07-17
**Status:** Active
**Type:** Requirements
**Specification:** [SPEC-LLAMAFILE-MINICPM5-1B](../specifications/SPEC-LLAMAFILE-MINICPM5-1B.md)

> Contract for producing self-contained, portable llamafile (APE) bundles for
> the MiniCPM5-1B model: a server bundle exposing an OpenAI-compatible HTTP
> endpoint on port 8765 and a chat bundle for interactive TUI use, both built
> from one CPU cosmocc engine. This document owns bundle requirements;
> build-mechanics detail lives in the companion specification. Explicitly
> excluded: native `llama.cpp` GPU flavor builds and the setup TUI (owned by
> [REQ-LLAMA-SETUP-TUI](REQ-LLAMA-SETUP-TUI.md)).

---

**Cross-references:**
- [SPEC-LLAMAFILE-MINICPM5-1B](../specifications/SPEC-LLAMAFILE-MINICPM5-1B.md): companion specification
- [SPEC-LLAMA-SETUP-TUI](../specifications/SPEC-LLAMA-SETUP-TUI.md): unified setup wizard (Vulkan bundles, systemd deploy)
- [`Makefile.llamafile`](../../Makefile.llamafile): bundle build targets
- [`models/minicpm5-1b/.args`](../../models/minicpm5-1b/.args): server default-args manifest (tracked)

---

## 1. Purpose & Scope

### 1.1 Purpose

Provide a single-file, double-clickable/CLI-runnable distribution of
MiniCPM5-1B that embeds the llamafile runtime, GGUF weights, and a default
argument manifest, so no host toolchain is required at run time.

### 1.2 Scope

**This document OWNS the requirements for:**
- CPU llamafile engine build (cosmocc, no root)
- Server and chat `.args` manifests and the bundles produced from them
- Bundle verification and artifact layout under `models/<name>/`

**This document DOES NOT:**
- Specify Vulkan/GPU bundles (see SPEC-LLAMA-SETUP-TUI)
- Specify systemd deployment (see SPEC-LLAMA-SETUP-TUI)
- Replace native `llama.cpp` builds

### 1.3 Terminology

| Term | Definition |
|------|------------|
| APE | Actually Portable Executable; runs on Linux/macOS/Windows/BSD, AMD64 + ARM64 (fat) |
| `.args` manifest | Zip entry read by `cosmo_args("/zip/.args")` supplying default CLI flags |
| Bundle | `llamafile` binary + GGUF + manifest combined into one APE file |
| cosmocc | Cosmopolitan cross compiler producing fat APE binaries |

## 2. Functional Requirements

### FR-1: Engine

| ID | Requirement |
|----|-------------|
| FR-1.1 | The engine MUST build with cosmocc from a pristine `mozilla-ai/llamafile` checkout without root and without `sudo make install`. |
| FR-1.2 | The engine MUST be CPU-only (no GPU code compiled in); the server manifest MUST pin `-ngl 0`. |
| FR-1.3 | The default build MUST be a fat APE (AMD64 + ARM64); an ARM64-only build MAY be produced for a smaller binary. |

### FR-2: Manifests and bundles

| ID | Requirement |
|----|-------------|
| FR-2.1 | Two manifests MUST be tracked in git: `models/minicpm5-1b/.args` (server) and `models/minicpm5-1b/.args.chat` (chat). |
| FR-2.2 | `make build-llamafile MODEL=minicpm5-1b MODE=server|chat|all` MUST embed the GGUF and the selected manifest as zip entry `.args` via zipalign. |
| FR-2.3 | The server bundle MUST serve an OpenAI-compatible HTTP API on port 8765 by default. |
| FR-2.4 | The chat bundle MUST launch an interactive TUI by default (`--chat`, no `--server`). |
| FR-2.5 | The mode MUST be chosen by the embedded manifest, never by recompiling the engine. |

### FR-3: Verification

| ID | Requirement |
|----|-------------|
| FR-3.1 | Bundle listings MUST show both the GGUF and `.args` as embedded entries. |
| FR-3.2 | The server bundle MUST respond on its HTTP endpoint after launch; the chat bundle MUST reach an interactive prompt. |

## 3. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1.1 | No root or host package installation for build or run. |
| NFR-1.2 | GGUF weights MUST NOT be committed to git (only `.args` manifests are tracked). |

## 4. Constraints

| ID | Constraint | Source |
|----|------------|--------|
| C-1 | GGUF source is `openbmb/MiniCPM5-1B-GGUF` (Q8_0 default) | Hugging Face |
| C-2 | Manifest must be embedded under the exact zip name `.args` | `cosmo_args` contract |

## 5. Assumptions

| ID | Assumption |
|----|------------|
| A-1 | MiniCPM5-1B loads on stock llamafile without custom kernels. |
| A-2 | Hosts provide sufficient RAM for Q8_0 inference on CPU. |

## 6. Open Questions

None.

## 7. Verification Matrix

| # | Test | Maps to |
|---|------|---------|
| V1 | `zipinfo` bundle listing shows GGUF + `.args` | FR-2.2, FR-3.1 |
| V2 | Launch server bundle; HTTP responds on 8765 | FR-2.3, FR-3.2 |
| V3 | Launch chat bundle; interactive prompt reached | FR-2.4, FR-3.2 |

## 8. Implementation Status

| Item | Status | Evidence |
|------|--------|----------|
| FR-1 CPU cosmocc engine build | Implemented | `scripts/setup/build-llama-cpu.sh` |
| FR-2 Manifests + `make build-llamafile` | Implemented | `models/minicpm5-1b/.args*`, `scripts/setup/build-llamafile-bundle.sh` |
| FR-3 Bundle verification | Implemented | SPEC Step 5 procedure |
| Vulkan server bundle | Implemented | `make build-llamafile-vulkan-bundle` (SPEC-LLAMA-SETUP-TUI) |
| systemd deploy (`install-llamafile`) | Implemented | `Makefile.llamafile`, `ansible/llamaserver.yml` |
