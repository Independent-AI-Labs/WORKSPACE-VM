# SPEC: Llama / Hardware Setup TUI

Entrypoint: `make llama-setup` (interactive) or `make llama-setup-ci` (defaults YAML).

## Motivation

Llama.cpp, llamafile, Intel GPU, and Vulkan probing were spread across:

- `make install` bootstrap checkboxes (build only, no deploy guidance)
- `Makefile.llamaserver` / `Makefile.llamafile` (operator targets)
- Ansible roles (systemd deploy)
- Duplicated Intel install scripts

This TUI unifies the full lifecycle: detect, prereqs, build, bundle, deploy, diagnose.

## Architecture

```
make llama-setup
  workspace/scripts/llama_setup_installer.py
    llama_setup_registry.py  <- workspace/config/llama-setup.yaml
    llama_setup_detect.py
    llama_setup_install.py   -> scripts/setup/*, Makefile.llama*
```

Follows `bootstrap_installer.py` patterns: `dataops.cli_components`, split UI/logic,
`stdin=DEVNULL` for child scripts, `--defaults` for CI.

## Issue catalogue (summary)

| Area | Key issues |
|------|------------|
| Duplication | Dual build entry (bootstrap + Make), Intel script overlap, musl PATH fix in two places |
| xpu-smi | Bootstrap ran full driver stack for monitoring-only; unused at runtime |
| Llama setup | Four blind checkboxes; no bundles/systemd in `make install` |
| GPU probe | python3 vs uv; triple vulkaninfo; silent MAIN_GPU=0 on failure |

See plan audit tables for IDs D1-D7, X1-X5, L1-L10, G1-G7.

## Consolidation

- `scripts/setup/install-intel-gpu.sh` with `--monitoring-only`, `--drivers`, `--oneapi`
- `scripts/setup/lib/gpu-toolchain-env.sh` shared PATH fix
- `vulkan_gpu_probe.py --cache-file` for single vulkaninfo parse per start
- Removed llama/gpu entries from `bootstrap-components.yaml`

## Related

- [SPEC-LLAMAFILE-MINICPM5-1B.md](SPEC-LLAMAFILE-MINICPM5-1B.md): bundle format