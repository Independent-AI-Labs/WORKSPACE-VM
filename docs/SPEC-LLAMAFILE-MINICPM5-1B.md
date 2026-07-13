# Specification: llamafile for MiniCPM5-1B

**Document ID:** WS-SPEC-LLAMAFILE-MINICPM5-v1.0
**Status:** Active (CPU sections); Vulkan/systemd extensions documented below
**Date:** 2026-07-06 (updated 2026-07-13)
**Classification:** Internal - Enterprise

> **Operator entrypoint (2026-07-13):** Use [`make llama-setup`](../README.md#llm-inference-llamafile-llama-cpp) for the full lifecycle (Intel/Vulkan prereqs, builds, bundles, systemd). This spec documents the **bundle format** and **CPU cosmocc build** in detail. Vulkan bundles, `ggml-vulkan.so`, and `install-llamafile` are covered in [`SPEC-LLAMA-SETUP-TUI.md`](SPEC-LLAMA-SETUP-TUI.md) and `Makefile.llamafile`.

**References:**
- mozilla-ai/llamafile `docs/source_installation.md`, `docs/creating_llamafiles.md`, `docs/technical_details.md`, `docs/support.md`
- mozilla-ai/llamafile `Makefile`, `build/config.mk`, `build/rules.mk` (fat-APE dual-compile evidence)
- cosmopolitan `tool/cosmocc/README.md` (cosmocc / cosmocross / apelink toolchain)
- OpenBMB/MiniCPM `docs/deployment/llama_cpp.md`
- Hugging Face model repo: `openbmb/MiniCPM5-1B-GGUF`
- Workspace: `Makefile.llamaserver`, `Makefile.llamafile`, `scripts/setup/build-llama-cpu.sh`, `scripts/setup/build-llamafile-bundle.sh`, `ansible/llamaserver.yml`

---

## Overview

This specification defines how to build **llamafile bundles** for MiniCPM5-1B:
single, self-contained, portable executables (APE format) that bundle the
llamafile runtime, GGUF weights, and a default argument manifest.

Two **CPU** bundles are produced from the same engine: a **server** bundle
(OpenAI-compatible HTTP on port 8765) and a **chat** bundle (interactive TUI).
The mode is chosen by which `.args` manifest is embedded.

A **Vulkan server** bundle (`*-vulkan.llamafile`) embeds `ggml-vulkan.so` and
`.args.vulkan`; see `make build-llamafile-vulkan-bundle` and
[`SPEC-LLAMA-SETUP-TUI.md`](SPEC-LLAMA-SETUP-TUI.md).

A llamafile is produced by combining three ingredients with `zipalign`:

1. The llamafile executable (cosmocc CPU engine under `projects/llamafile/o/`)
2. MiniCPM5-1B weights in GGUF format (`models/minicpm5-1b/`)
3. A `.args` manifest (`.args`, `.args.chat`, or `.args.vulkan`)

**CPU build stack:** cosmocc + GNU make + `zipalign`. No root required for the
engine/bundle build itself. **Vulkan** additionally requires `ggml-vulkan.so`
(build script + host Vulkan dev packages).

---

## Scope & Non-Goals

### In Scope
- Build the llamafile runtime **from source** as a guaranteed CPU-only APE binary.
- Ship a single **fat APE covering AMD64 + ARM64**; the ARM64 slice is
  cross-compiled automatically from the x86_64 build host (no extra toolchain).
  An optional ARM64-only build path is also documented.
- Bundle the released `MiniCPM5-1B-Q8_0.gguf` into a single distributable
  `.llamafile` whose default action is to serve an OpenAI-compatible HTTP API.
- Pin the default decoding mode to **No-think, temperature 0** (greedy).

### Non-Goals (this document)
- This is **not** a replacement for native `llama.cpp` builds (`make build-llama
  FLAVOR=*` → `llamaserver@<flavor>`). Llamafile targets portable single-file
  distribution; llama.cpp targets host-native `llama-server` binaries.
- CUDA and SYCL backends for llamafile are out of scope (use `llamaserver@sycl`
  or `make llama-setup` stack `llama_cpp_sycl` instead).

### Extensions (implemented elsewhere; not detailed in original CPU sections)
- **Vulkan GPU:** `make build-llamafile-vulkan-bundle`, headless GPU auto-select
  via `scripts/setup/lib/vulkan_gpu_probe.py`. See `Makefile.llamafile` and
  [`SPEC-LLAMA-SETUP-TUI.md`](SPEC-LLAMA-SETUP-TUI.md).
- **systemd deploy:** `make install-llamafile MODEL=minicpm5-1b` deploys
  `llamafile-<model>.service` (user unit) via `ansible/llamafile.yml`.
- **Bootstrap:** llama/GPU components are **not** in `make install`; use
  `make llama-setup`.

---

## Background

### Why CPU-only is the default cosmocc engine build
llamafile combines `llama.cpp` with Cosmopolitan Libc. The cosmocc source
build compiles **no GPU code**. The resulting APE binary performs pure CPU
inference with runtime SIMD dispatch:
- AMD64 requires AVX (Intel Core 2006+, AMD K8 2003+); AVX2 / FMA / F16C /
  VNNI / AVX512 are conditionally enabled at runtime on newer CPUs.
- ARM64 requires ARMv8a+ (Apple Silicon, 64-bit Raspberry Pi, etc.).

GPU support in llamafile is opt-in via dynamic runtime loading of host GPU
libraries; if absent, it falls back to CPU. This spec produces a binary with
no GPU code compiled in, and pins `-ngl 0` in `.args` so CPU inference is
explicit even on GPU-capable hosts.

### Why MiniCPM5-1B loads without custom kernels
MiniCPM5-1B is a dense 1.08B-parameter Transformer using the **standard
`LlamaForCausalLM` architecture** (24 layers, GQA 16Q/2KV, 131072 context).
Any recent `llama.cpp` - including the version bundled inside llamafile -
loads it directly. No model-code fork, no custom kernels.

### Released GGUF artifacts (source: `openbmb/MiniCPM5-1B-GGUF`)
| File | Size | Use case |
| --- | --- | --- |
| `MiniCPM5-1B-F16.gguf` | 2.17 GB | reference quality, most uniform CPU perf |
| `MiniCPM5-1B-Q8_0.gguf` | 1.15 GB | minimal quality drop vs F16, half the disk **(selected)** |
| `MiniCPM5-1B-Q4_K_M.gguf` | 688 MB | edge / mobile-class hardware |

**Selection: Q8_0** - best all-rounder for a 1B model on CPU (small quality
delta vs F16, fast, reasonable footprint).

---

## Architecture Support: Fat APE (AMD64 + ARM64)

A single llamafile binary runs **natively on both AMD64 and ARM64**. This is
not an optional extra build - it is the **default** behavior of the cosmocc
build, and it is achieved without any cross-gcc, QEMU, or extra toolchain on
the build host.

### How the fat binary is produced
llamafile builds `llama.cpp` **twice** - once for AMD64, once for ARM64 - and
joins the two ELF images into one APE file wrapped by a polyglot shell script
(with an `MZ` prefix). At launch the wrapper dispatches to the matching arch.

This is visible directly in the llamafile build system:
- `build/config.mk` sets `CC = $(TOOLCHAIN)cc` where `TOOLCHAIN = .cosmocc/4.0.2/bin/cosmo`, i.e. the `cosmocc` **fat** driver (not a single-arch compiler), and defines `CPPFLAGS_ = ... -DGGML_MULTIPLATFORM ...`.
- `build/rules.mk` compiles **every** object and archive for both ISAs: each `o/$(MODE)/<pkg>/%.o` is paired with a sibling at `o/$(MODE)/<pkg>/.aarch64/<name>.o`, and each `%.a` archive rule emits both `o/$(MODE)/.../<name>.a` and `o/$(MODE)/.../.aarch64/<name>.a`. The `apelink` step (invoked by the cosmocc driver at link time) fuses the two into one fat APE.

**Consequence:** the default `.cosmocc/4.0.2/bin/make -j"$(nproc)"` already
emits a fat `o/llamafile/llamafile` containing AMD64 + ARM64 code. There is
no separate "ARM64 build" step to remember.

### Cross-compile is built-in (no extra toolchain)
`cosmocc` is a Linux-hosted toolchain that always emits both ISAs regardless
of the build host's own architecture. Building on the workspace's **x86_64**
sandbox therefore **cross-compiles ARM64 into the fat binary automatically** -
no `aarch64-linux-gnu-gcc`, no QEMU, no `dpkg --add-architecture` required.

> Requirement met natively: the spec must support **ARM64**, both on-device
> and via cross-compile. The default fat-APE build satisfies both at once:
> the ARM64 slice is cross-compiled from the x86_64 build host, and the
> resulting single file runs on ARM64 hosts without recompilation.

### ARM64-only build (optional, smaller binary)
If a smaller, ARM64-only artifact is ever wanted (drops the AMD64 slice),
override the toolchain to the single-arch cosmocc wrappers - no Makefile
changes needed, just `CC`/`CXX`:

```sh
# From projects/llamafile/, after `make setup`:
.cosmocc/4.0.2/bin/make -j"$(nproc)" \
  CC=.cosmocc/4.0.2/bin/aarch64-unknown-cosmo-cc \
  CXX=.cosmocc/4.0.2/bin/aarch64-unknown-cosmo-c++
# → o/llamafile/llamafile is now ARM64-only (non-fat)
```

This is an advanced variant. The **default fat build is recommended** for
this spec because a single distributable covering both ISAs is the whole
point of shipping a llamafile. The ARM64-only path is documented here for
completeness and for any future edge-device (e.g. Raspberry Pi 4/5) release
where the AMD64 slice is dead weight.

### Supported OS × ISA matrix (runtime)
Per llamafile `docs/support.md`. The fat APE covers the union; CPU-only mode
(`-ngl 0`) is used everywhere.

| OS | AMD64 | ARM64 | Notes |
| --- | :---: | :---: | --- |
| Linux 2.6.18+ | ✅ | ✅ | Primary target; both ISAs fully supported |
| Darwin (macOS) 23.1.0+ | ✅ | ✅ | Metal GPU is ARM64-only, but disabled here via `-ngl 0` |
| Windows 10+ | ✅ | ❌ | AMD64 only; Windows-on-ARM not supported by APE |
| FreeBSD 13+ | ✅ | ✅ | Both ISAs |
| NetBSD 9.2+ | ✅ | ❌ | AMD64 only |
| OpenBSD 7.0-7.4 | ✅ | ❌ | AMD64 only |

### ARM64 runtime prerequisites
- **CPU:** ARMv8a+ (Apple Silicon, 64-bit Raspberry Pi 3B+/4/5, Graviton, etc.).
- **APE loader (one-time, recommended):** On UNIX the fat APE self-extracts an
  ~8 KB loader to `$TMPDIR/.ape` (or `$HOME/.ape`). For faster, more reliable launch,
  install it systemwide - **requires root**, so on the workspace this is an
  operator task, not an agent task:
  - Linux ARM64: copy `ape-aarch64.elf` → `/usr/bin/ape`, optionally register `binfmt_misc`.
  - Apple ARM64 (M1+): compile `cc -O -o ape bin/ape-m1.c` → `/usr/local/bin/ape` (needs Xcode CLT).
- **GPU:** ARM64 macOS can use Metal, but this spec pins `-ngl 0` → pure CPU.
- **RAM:** ≥ 1.5 GB free for Q8_0 weights + KV cache at `-c 8192`.

### Assimilate (optional, native-format conversion)
The cosmocc-bundled `assimilate` tool can rewrite the fat APE into the host's
native executable format (e.g. a plain Linux ARM64 ELF), removing the
shell-script/loader hop. This is only needed to satisfy restrictive release
pipelines that reject polyglot binaries. Not required for normal operation.

---

## Architecture / Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  mozilla-ai/llamafile  (git clone → projects/llamafile/)         │
│  make setup        → inits submodules + downloads cosmocc         │
│                     into projects/llamafile/.cosmocc/             │
│  cosmocc make -j   → build outputs in projects/llamafile/o/       │
│    ├── o/llamafile/llamafile            (CPU-only fat APE:        │
│    │                                     AMD64 + ARM64, default)  │
│    └── o/third_party/zipalign/zipalign (APE zip bundler)          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌────────────────┐   ┌──────────────────┐   ┌────────────────────┐
│ o/llamafile/   │   | models/minicpm5-  │   │ .args manifest     │
│   llamafile    │   │ 1b/MiniCPM5-1B-   │   │ (server, temp 0,   │
│ (fat APE:      │   │   Q8_0.gguf        │   │  -ngl 0, /zip/…)   │
│  AMD64+ARM64)  │   │                    │   │                    │
└───────┬────────┘   └─────────┬────────┘   └──────────┬─────────┘
        │                      │                       │
        └──────────────────────┼───────────────────────┘
                               ▼
                 ┌──────────────────────────┐
                 │ zipalign -j0             │
                 │   (embed gguf + .args    │
                 │    into the APE binary)  │
                 └──────────────┬───────────┘
                                ▼
           ┌─────────────────────────────────────────────┐
           │ models/minicpm5-1b/MiniCPM5-1B-Q8_0.llamafile │
           │ (single self-contained portable executable)   │
           └─────────────────────────────────────────────┘
                                │
                                ▼ on launch (default .args)
                 OpenAI-compatible HTTP server (0.0.0.0:8765)
```

---

## Build Decisions (locked)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Runtime binary | **Build from source** (cosmocc) | Guaranteed CPU-only APE; no GPU code compiled in |
| Target architectures | **AMD64 + ARM64** (fat APE, default) | One file runs on both ISAs; ARM64 cross-compiled automatically from the x86_64 build host |
| Quantization | **Q8_0** (1.15 GB) | Minimal quality drop vs F16; CPU-fast; sane footprint |
| Default mode | **Server + Chat** (two bundles) | Server bundle = OpenAI HTTP endpoint; chat bundle = interactive TUI. Mode chosen by embedded `.args`, not by recompiling |
| Server port | **8765** | Exotic port; avoids collision with workspace llamaserver flavors (8080/8081/8082) and the sandbox `rootlessport` on 8080 |
| Decode mode | **No-think, temp 0** | Deterministic/greedy; latency-bound assistant default |

---

## File & Path Layout

Aligned with existing workspace conventions (`projects/llama.cpp/`,
`models/<model>.gguf`):

| Path | Purpose | Tracked? |
| --- | --- | --- |
| `projects/llamafile/` | llamafile source tree (git clone) | **Gitignored** |
| `projects/llamafile/.cosmocc/` | cosmocc compiler (downloaded by `make setup`) | Gitignored |
| `projects/llamafile/o/` | build outputs (`llamafile`, `zipalign`) | Gitignored |
| `models/minicpm5-1b/MiniCPM5-1B-Q8_0.gguf` | downloaded GGUF weights | Gitignored |
| `models/minicpm5-1b/.args` | server default-args manifest | **Git** |
| `models/minicpm5-1b/.args.chat` | chat default-args manifest | **Git** |
| `models/minicpm5-1b/MiniCPM5-1B-Q8_0.llamafile` | server distributable artifact | Gitignored (large) |
| `models/minicpm5-1b/MiniCPM5-1B-Q8_0-chat.llamafile` | chat distributable artifact | Gitignored (large) |
| `Makefile.llamafile` | bundle build/clean targets | **Git** |
| `scripts/setup/build-llamafile-bundle.sh` | bundle build script | **Git** |

> The `.args` / `.args.chat` files are tracked because they are the source of
> truth for each bundle's default behavior - small, human-readable, reviewable.
> All binary/large artifacts are gitignored. The `models/` tree is gitignored
> but `.gitignore` re-includes `models/*/.args` and `models/*/.args.*` so the
> manifests are trackable without `-f`.

---

## Step-by-Step Procedure

### Step 1 - Build the CPU-only llamafile toolchain (no root)

Requires only `make`, `sha256sum`, `wget`/`curl`, `unzip` (all present in the
sandbox). `sudo make install` is intentionally **skipped**; binaries are used
straight from `o/`.

```sh
git clone https://github.com/mozilla-ai/llamafile.git projects/llamafile
cd projects/llamafile
make setup                                 # init submodules + download cosmocc
.cosmocc/4.0.2/bin/make -j"$(nproc)"       # fat APE: AMD64 + ARM64 in one binary
make check                                 # optional unit tests
ls -l o/llamafile/llamafile o/third_party/zipalign/zipalign
cd -  # back to repo root
```

> The `cosmocc` driver is Linux-hosted and always emits **both** ISAs, so
> building on this x86_64 sandbox **cross-compiles the ARM64 slice into the
> fat binary automatically** - no cross-gcc or QEMU on the build host needed.
> The single `o/llamafile/llamafile` then runs natively on AMD64 and ARM64.

Optional - ARM64-only (smaller, non-fat) binary, e.g. for an edge device:

```sh
# From projects/llamafile/ (after `make setup`):
.cosmocc/4.0.2/bin/make -j"$(nproc)" \
  CC=.cosmocc/4.0.2/bin/aarch64-unknown-cosmo-cc \
  CXX=.cosmocc/4.0.2/bin/aarch64-unknown-cosmo-c++
```

**Acceptance:** both `projects/llamafile/o/llamafile/llamafile` and
`projects/llamafile/o/third_party/zipalign/zipalign` exist and are executable.
The runner is a fat APE (see "Architecture Support" above).

### Step 2 - Download the GGUF

```sh
mkdir -p models/minicpm5-1b
huggingface-cli download openbmb/MiniCPM5-1B-GGUF \
  MiniCPM5-1B-Q8_0.gguf --local-dir models/minicpm5-1b
```

**Acceptance:** `models/minicpm5-1b/MiniCPM5-1B-Q8_0.gguf` present, ~1.15 GB.

### Step 3 - Write the `.args` manifests

Two manifests are tracked, one per default mode. Both use one argument per
line; the `/zip/` prefix references files embedded inside the llamafile; the
trailing `...` token injects any runtime CLI arguments the user passes.

**Server manifest** - `models/minicpm5-1b/.args` (HTTP server default):

```
-m
/zip/MiniCPM5-1B-Q8_0.gguf
--jinja
--server
--host
0.0.0.0
--port
8765
-ngl
0
--temp
0
--top-p
0.95
-c
8192
--no-mmap
--reasoning
off
...
```

**Chat manifest** - `models/minicpm5-1b/.args.chat` (interactive TUI default):

```
-m
/zip/MiniCPM5-1B-Q8_0.gguf
--jinja
--chat
-ngl
0
--temp
0
--top-p
0.95
-c
8192
--no-mmap
--reasoning
off
...
```

> The chat manifest omits `--server`, `--host`, and `--port` because those
> flags are registered `LLAMA_EXAMPLE_SERVER`-only in llama.cpp's arg parser
> (`common/arg.cpp`); in `--chat` mode the engine parses with
> `LLAMA_EXAMPLE_CLI` (llamafile `main.cpp:139`), so server-only flags would
> error. `--jinja` and `--reasoning` are valid in both examples and are kept.
> The mode is chosen purely by which manifest is embedded - the engine binary
> is identical across modes (no recompile). `args.cpp:69` checks `--server`
> before `--chat`, so a bundle that embeds `--server` can never fall back to
> chat at runtime; the chat bundle therefore embeds `--chat` and no
> `--server`.

### Step 4 - Bundle via build automation

Bundling is automated by `Makefile.llamafile` + `scripts/setup/build-llamafile-bundle.sh`.
The script reuses the prebuilt engine + zipalign (Step 1), stages the chosen
manifest as the zip entry `.args` (required by `cosmo_args("/zip/.args")`),
and runs `zipalign -j0` to embed the GGUF + manifest into a copy of the engine.
No recompile; the engine is identical across modes.

```sh
# Server-default bundle  -> MiniCPM5-1B-Q8_0.llamafile
make build-llamafile MODEL=minicpm5-1b MODE=server

# Chat-default bundle    -> MiniCPM5-1B-Q8_0-chat.llamafile
make build-llamafile MODEL=minicpm5-1b MODE=chat

# Both
make build-llamafile MODEL=minicpm5-1b            # MODE defaults to all

# Remove built bundles
make clean-llamafile MODEL=minicpm5-1b
```

**Acceptance:** `unzip -vl models/minicpm5-1b/MiniCPM5-1B-Q8_0.llamafile`
lists both the GGUF and `.args` as embedded entries; the chat bundle lists
`.args` containing `--chat` and no `--server`.

### Step 5 - Verify

```sh
# --- Server bundle ---
OUT=models/minicpm5-1b/MiniCPM5-1B-Q8_0.llamafile
unzip -vl "$OUT"                       # confirm embedded gguf + .args
file "$OUT"                            # polyglot: DOS/MBR + ELF (fat APE)
"$OUT" --version                       # AMD64 slice launches on this host
"$OUT" &                               # launch server on 0.0.0.0:8765
SERVER_PID=$!
sleep 5
curl -s http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniCPM5-1B","messages":[{"role":"user","content":"1+1=?"}],"max_tokens":64}'
kill "$SERVER_PID"

# --- Chat bundle (no HTTP listener) ---
CHAT=models/minicpm5-1B/MiniCPM5-1B-Q8_0-chat.llamafile
unzip -vl "$CHAT"                      # .args has --chat, no --server
printf 'What is 1+1? Reply with just the number.\n' | "$CHAT"
# expect: a TUI reply (e.g. "2") and NO listener opened by the process
```

> **ARM64 verification:** the AMD64 slice is exercised above on the build
> host. The ARM64 slice cannot run on an x86_64 host; it is verified
> structurally (the `.aarch64/` sibling objects exist in the build tree and
> `apelink` produced a fat APE) and functionally by launching the same
> `.llamafile` on an ARM64 host (Apple Silicon / Linux aarch64 / Graviton) or
> under `qemu-aarch64` if installed. The bundled GGUF and `.args` are
> ISA-independent, so no re-bundle is needed per architecture.

---

## `.args` Manifest Semantics

| Arg | Value | Meaning |
| --- | --- | --- |
| `-m` | `/zip/MiniCPM5-1B-Q8_0.gguf` | Model path inside the embedded zip namespace |
| `--jinja` | - | Apply the chat template baked into the GGUF (MiniCPM5 chat format) |
| `--server` | - | Run as OpenAI-compatible HTTP server (not TUI) |
| `--host` | `0.0.0.0` | Bind all interfaces |
| `--port` | `8765` | Listen port (server manifest only) |
| `-ngl` | `0` | Zero GPU layers offloaded → force CPU (makes CPU-only intent explicit) |
| `--temp` | `0` | Greedy decoding (No-think, deterministic) |
| `--top-p` | `0.95` | Inert at temp 0; retained for clarity / easy mode switching |
| `-c` | `8192` | Context window (model supports 131072; 8192 bounds RAM for CPU) |
| `--no-mmap` | - | Force weights resident in RAM (matches llamafile example .args); optional |
| `--reasoning` | `off` | Disable thinking/reasoning mode; responses go straight to `content` (no `reasoning_content`) |
| `...` | - | Pass-through token for user runtime overrides |

**Mode switching at runtime** (the `...` token allows overrides):
- Think mode: `./MiniCPM5-1B-Q8_0.llamafile --reasoning on --temp 0.9`
- Different port: `./MiniCPM5-1B-Q8_0.llamafile --port 8081`
- TUI chat: use the chat-default bundle
  `./MiniCPM5-1B-Q8_0-chat.llamafile` (embeds `--chat`, no `--server`).
  The server-default bundle cannot be switched to chat at runtime because
  `args.cpp:69` checks `--server` before `--chat` and the embedded `.args`
  always supplies `--server`; the chat bundle is the supported path to TUI.

---

## Runtime Notes & Constraints

### Port registry (workspace host co-location)
The workspace `ansible/llamaserver.yml` reserves: cpu=8081, sycl=8082,
vulkan=8080. The llamafile server bundle defaults to **8765** - an exotic
port chosen to avoid collision with any workspace llamaserver flavor and
with the sandbox's `rootlessport` forwarder on 8080. Override at launch if
needed: `./MiniCPM5-1B-Q8_0.llamafile --port <PORT>`. The chat bundle opens
no listener at all.

### Temperature 0 & reasoning-off semantics
At `--temp 0` decoding is greedy; `--top-p` has no effect. With `--reasoning off`
the model produces answers directly in `message.content` without a thinking
phase, yielding deterministic, low-latency output suitable for an on-device
assistant. To use MiniCPM5-1B's Think setting, override at runtime:
`./MiniCPM5-1B-Q8_0.llamafile --reasoning on --temp 0.9`.

### CPU requirements
- AMD64: AVX minimum (Intel Core 2006+ / AMD K8 2003+).
- ARM64: ARMv8a+ (Apple Silicon, 64-bit Raspberry Pi).
- RAM: ≥ 1.5 GB free for the Q8_0 weights + KV cache at `-c 8192`.

### Build environment (sandbox)
This build requires no root. The `sudo make install` step from the upstream
instructions is skipped; binaries are consumed directly from
`projects/llamafile/o/`. If system-wide installation is later desired, that
step requires root and must be requested from the operator.

---

## Acceptance Criteria

- [x] `projects/llamafile/o/llamafile/llamafile` built (CPU-only cosmocc **fat APE**)
- [x] Fat binary contains both ISAs: `.aarch64/` sibling objects present in the build tree; `file` reports polyglot DOS/MBR+ELF
- [x] ARM64 slice cross-compiled from the x86_64 build host (no cross-gcc/QEMU used during build)
- [x] `projects/llamafile/o/third_party/zipalign/zipalign` built
- [x] `models/minicpm5-1b/MiniCPM5-1B-Q8_0.gguf` downloaded (~1.15 GB)
- [x] `models/minicpm5-1b/.args` written (server manifest, port 8765)
- [x] `models/minicpm5-1b/.args.chat` written (chat manifest, `--chat`, no server-only flags)
- [x] `models/minicpm5-1b/MiniCPM5-1B-Q8_0.llamafile` produced and executable (server default)
- [x] `models/minicpm5-1b/MiniCPM5-1B-Q8_0-chat.llamafile` produced and executable (chat default)
- [x] `unzip -vl` confirms GGUF + `.args` embedded in both bundles
- [x] Server bundle: embedded `.args` has `--server` + `--port 8765`
- [x] Chat bundle: embedded `.args` has `--chat`, no `--server`/`--host`/`--port`
- [x] AMD64 slice: server bundle serves HTTP on 0.0.0.0:8765 and answers `/v1/chat/completions`
- [x] Chat bundle: TUI launches on piped prompt, produces a reply, opens NO listener
- [ ] ARM64 slice: same `.llamafile` launches and serves on an ARM64 host (or under `qemu-aarch64`)

---

## References

- llamafile source installation: https://github.com/mozilla-ai/llamafile/blob/main/docs/source_installation.md
- Creating llamafiles (zipalign bundling): https://github.com/mozilla-ai/llamafile/blob/main/docs/creating_llamafiles.md
- llamafile technical details (fat APE / dual-arch): https://github.com/mozilla-ai/llamafile/blob/main/docs/technical_details.md
- llamafile supported systems (OS × ISA matrix): https://github.com/mozilla-ai/llamafile/blob/main/docs/support.md
- cosmocc toolchain (cosmocc / cosmocross / apelink): https://github.com/jart/cosmopolitan/blob/master/tool/cosmocc/README.md
- MiniCPM5-1B llama.cpp deployment: https://github.com/OpenBMB/MiniCPM/blob/main/docs/deployment/llama_cpp.md
- GGUF model repo: https://huggingface.co/openbmb/MiniCPM5-1B-GGUF
- Workspace native CPU build (distinct): `scripts/setup/build-llama-cpu.sh`, `Makefile.llamaserver`
- Workspace llamafile bundle automation: `Makefile.llamafile`, `scripts/setup/build-llamafile-bundle.sh`
