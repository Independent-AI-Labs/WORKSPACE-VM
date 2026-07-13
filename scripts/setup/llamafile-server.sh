#!/usr/bin/env bash
# Runtime wrapper for llamafile systemd services.
#
# 1. Fixes PATH and cosmo dlopen-helper for Vulkan DSO loading
# 2. Loads ~/.config/llamafile/llamafile-<model>.env (systemd EnvironmentFile)
# 3. Auto-selects best Vulkan GPU when LLAMAFILE_MAIN_GPU=auto
# 4. Maps LLAMAFILE_* tuning knobs to LLAMA_ARG_* env vars
# 5. exec /bin/sh <bundle.llamafile> with no CLI args (preserves embedded .args)
#
# Usage: llamafile-server.sh <path-to.llamafile>
set -euo pipefail

if [ "$#" -lt 1 ]; then
    printf 'usage: %s <bundle.llamafile>\n' "$0" >&2
    exit 2
fi

BUNDLE_PATH="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/llamafile-gpu-env.sh
source "$SCRIPT_DIR/lib/llamafile-gpu-env.sh" || exit 1

llamafile_gpu_env_init
ensure_cosmo_dlopen_helper

export LLAMAFILE_PATH="$BUNDLE_PATH"

if [ ! -f "$BUNDLE_PATH" ]; then
    printf 'error: bundle not found: %s\n' "$BUNDLE_PATH" >&2
    exit 1
fi

# Derive GGUF path for VRAM estimates when not set in EnvironmentFile.
if [ -z "${LLAMAFILE_MODEL_GGUF:-}" ]; then
    model_dir="$(dirname "$BUNDLE_PATH")"
    gguf_count=0
    gguf_path=""
    while IFS= read -r -d '' f; do
        gguf_path="$f"
        gguf_count=$((gguf_count + 1))
    done < <(find "$model_dir" -maxdepth 1 -type f -name '*.gguf' -print0)
    if [ "$gguf_count" -eq 1 ]; then
        export LLAMAFILE_MODEL_GGUF="$gguf_path"
    fi
fi

# Parallel slots + GPU selection (may set LLAMA_ARG_*).
while IFS= read -r line; do
    case "$line" in
        LLAMA_ARG_*|LLAMAFILE_MAIN_GPU=*)
            export "$line"
            ;;
    esac
done < <(bash "$SCRIPT_DIR/compute-llamafile-parallel.sh")

if [ -n "${LLAMAFILE_THREADS:-}" ] && [ "${LLAMAFILE_THREADS}" != "0" ]; then
    export LLAMA_ARG_THREADS="$LLAMAFILE_THREADS"
fi

if [ -n "${LLAMAFILE_SPLIT_MODE:-}" ]; then
    export LLAMA_ARG_SPLIT_MODE="$LLAMAFILE_SPLIT_MODE"
fi

if [ -n "${LLAMAFILE_TENSOR_SPLIT:-}" ]; then
    export LLAMA_ARG_TENSOR_SPLIT="$LLAMAFILE_TENSOR_SPLIT"
fi

if [ -n "${LLAMAFILE_MAIN_GPU:-}" ] && [ "${LLAMAFILE_MAIN_GPU}" != "auto" ]; then
    export LLAMA_ARG_MAIN_GPU="$LLAMAFILE_MAIN_GPU"
fi

exec /bin/sh "$BUNDLE_PATH"