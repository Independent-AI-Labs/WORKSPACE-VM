# SPEC: Llama / Hardware Setup TUI

**Status:** Active
**Type:** Specification
**Requirements:** [REQ-LLAMA-SETUP-TUI](../requirements/REQ-LLAMA-SETUP-TUI.md)
**Entrypoints:** `make llama-setup` (interactive), `make llama-setup-ci` (defaults YAML)

## Motivation

Llama.cpp, llamafile, Intel GPU, and Vulkan probing were spread across `make install` checkboxes, `Makefile.llamaserver` / `Makefile.llamafile`, Ansible roles, and duplicated Intel install scripts. This TUI unifies detect, prereqs, build, bundle, deploy, and diagnose.

Llama and GPU components were **removed** from `make install`. Use this TUI instead.

## Quick start

```bash
make llama-setup          # interactive wizard
make llama-setup-ci       # non-interactive (llamafile Vulkan server profile)
```

Registry: [`workspace/config/llama-setup.yaml`](../../workspace/config/llama-setup.yaml)
CI defaults: [`workspace/config/llama-setup-defaults.yaml`](../../workspace/config/llama-setup-defaults.yaml)

## Wizard phases

| Phase | What happens | Sudo |
| :--- | :--- | :--- |
| 1. Hardware detect | `render`/`video` groups, `xpu-smi`, `vulkaninfo`, Vulkan GPU probe, existing builds/services | No |
| 2. Prereqs | Intel drivers, Vulkan dev, oneAPI (per stack) via `install-intel-gpu.sh` flags | Yes |
| 3. Build stack | Guided profile builds (engine, DSO, llama.cpp) | No |
| 4. Bundle model | `.llamafile` bundles under `models/<name>/` | No |
| 5. Deploy service | Ansible: `llamafile-<model>` or `llamaserver@<flavor>` user units | No |
| 6. Diagnostics | Vulkan probe, optional `xpu-smi stats`, `test-llamafile-vulkan` | No |

Child scripts run with `stdin=DEVNULL` so they never steal the TUI terminal.

## Stack profiles

Defined in `llama-setup.yaml`:

| ID | Label | Deploy |
| :--- | :--- | :--- |
| `llamafile_vulkan_server` | Llamafile Vulkan server (recommended) | `llamafile-<model>` systemd unit |
| `llama_cpp_vulkan` | llama.cpp Vulkan | `llamaserver@vulkan` |
| `llama_cpp_sycl` | llama.cpp SYCL | `llamaserver@sycl` |
| `llama_cpp_cpu` | llama.cpp CPU | `llamaserver@cpu` |
| `llamafile_cpu_chat` | Llamafile CPU chat TUI | None (local binary) |

## Prereq scripts

| ID | Script | Flags |
| :--- | :--- | :--- |
| `intel_drivers` | `scripts/setup/install-intel-gpu.sh` | `--drivers` |
| `intel_monitoring` | same | `--monitoring-only` (xpu-smi + clinfo only) |
| `vulkan_dev` | `scripts/setup/install-vulkan-dev.sh` | (full script) |
| `oneapi` | `scripts/setup/install-intel-gpu.sh` | `--oneapi` |

After Intel driver install, run `newgrp render` or re-login before GPU probes succeed.

## Architecture

```
make llama-setup
  workspace/scripts/llama_setup_installer.py
    llama_setup_registry.py   <- workspace/config/llama-setup.yaml
    llama_setup_detect.py
    llama_setup_install.py    -> scripts/setup/*, Makefile.llama*
```

Follows `bootstrap_installer.py` patterns (`dataops.cli_components`, split UI/logic).

## Makefile escape hatches

The TUI delegates to existing Make targets. For scripting:

```bash
make -f Makefile.llamafile build-llamafile-vulkan-bundle MODEL=minicpm5-1b
make -f Makefile.llamafile install-llamafile MODEL=minicpm5-1b GPU=vulkan
make -f Makefile.llamaserver build-llama FLAVOR=vulkan
make -f Makefile.llamaserver install-llamaserver FLAVOR=vulkan
```

## Consolidation notes

- `scripts/setup/install-intel-gpu.sh`: `--monitoring-only`, `--drivers`, `--oneapi`
- `scripts/setup/lib/gpu-toolchain-env.sh`: shared musl PATH fix for GPU builds
- `vulkan_gpu_probe.py --cache-file`: single vulkaninfo parse per service start
- Removed from `bootstrap-components.yaml`: `llama_*`, `llamafile_vulkan`, `intel_xpu_smi`

## Related

- [SPEC-LLAMAFILE-MINICPM5-1B.md](SPEC-LLAMAFILE-MINICPM5-1B.md): bundle format and CPU build background
- [../benchmarks/llamafile/transcript_classifier/README.md](../../benchmarks/llamafile/transcript_classifier/README.md): benchmark (requires running server)