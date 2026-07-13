#!/usr/bin/env bash
# Estimate llamafile server parallel slots from free GPU memory.
#
# When LLAMAFILE_MAIN_GPU is unset or "auto" and multiple discrete Vulkan GPUs
# are present, prefers devices with zero connected monitors (headless) so the
# display GPU is not saturated, then picks the most available device-local
# memory (budget - usage) and pins the server to that single GPU.
#
# Outputs shell-assignable variables on stdout:
#   LLAMAFILE_MAIN_GPU=<index>
#   LLAMA_ARG_MAIN_GPU=<index>
#   LLAMA_ARG_N_PARALLEL=<slots>
#
# Environment (read from caller / EnvironmentFile):
#   LLAMAFILE_MAIN_GPU       auto | integer (default: auto)
#   LLAMAFILE_PARALLEL       auto | integer (default: auto)
#   LLAMAFILE_PARALLEL_MAX   optional hard cap (unset = VRAM-only limit)
#   LLAMAFILE_PARALLEL_RESERVE  when probe fails (default: 4)
#   LLAMAFILE_CTX            context size (default: 8192)
#   LLAMAFILE_VRAM_MARGIN_MIB  reserved MiB (default: 1024)
#   LLAMAFILE_MODEL_GGUF     path to weights (required for auto)
#   LLAMAFILE_SPLIT_MODE     passed through (default: none)
#   LLAMAFILE_TENSOR_SPLIT   optional pin, e.g. 1,0 for single GPU
#
# KV estimate (conservative, no GGUF parse):
#   kv_mib_per_slot = (ctx / 8192) * model_mib * 0.75
# Tunable override: LLAMAFILE_KV_MIB_PER_SLOT
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/llamafile-gpu-env.sh
source "$SCRIPT_DIR/lib/llamafile-gpu-env.sh" || exit 1

llamafile_gpu_env_init

main_gpu="${LLAMAFILE_MAIN_GPU:-auto}"
parallel="${LLAMAFILE_PARALLEL:-auto}"
parallel_max="${LLAMAFILE_PARALLEL_MAX:-}"
parallel_reserve="${LLAMAFILE_PARALLEL_RESERVE:-4}"
ctx="${LLAMAFILE_CTX:-8192}"
margin_mib="${LLAMAFILE_VRAM_MARGIN_MIB:-1024}"
split_mode="${LLAMAFILE_SPLIT_MODE:-none}"
model_gguf="${LLAMAFILE_MODEL_GGUF:-}"

probe_vulkan_gpus() {
    if ! command -v vulkaninfo >/dev/null 2>&1; then
        return 1
    fi
    python3 "$SCRIPT_DIR/lib/vulkan_gpu_probe.py"
}

select_best_gpu_index() {
    local picked=""
    picked="$(uv run python "$SCRIPT_DIR/lib/vulkan_gpu_probe.py" --select-best)"
    pick_rc=$?
    if [ "$pick_rc" -ne 0 ] || [ -z "$picked" ]; then
        return 1
    fi
    if [ -z "$picked" ]; then
        return 1
    fi
    printf '%s\n' "$picked"
}

resolve_main_gpu() {
    case "$main_gpu" in
        auto|""|"-1")
            local picked
            if ! picked="$(select_best_gpu_index)"; then
                printf 'warning: Vulkan GPU probe failed; using MAIN_GPU=0\n' >&2
                printf '0\n'
                return
            fi
            local picked_monitors="" picked_pci="" picked_name="" in_pick=0
            while IFS= read -r line; do
                case "$line" in
                    GPU_INDEX=*)
                        if [ "${line#GPU_INDEX=}" = "$picked" ]; then
                            in_pick=1
                        else
                            in_pick=0
                        fi
                        ;;
                    MONITOR_COUNT=*)
                        if [ "${in_pick:-0}" -eq 1 ]; then
                            picked_monitors="${line#MONITOR_COUNT=}"
                        fi
                        ;;
                    PCI_SLOT=*)
                        if [ "${in_pick:-0}" -eq 1 ]; then
                            picked_pci="${line#PCI_SLOT=}"
                        fi
                        ;;
                    DEVICE_NAME=*)
                        if [ "${in_pick:-0}" -eq 1 ]; then
                            picked_name="${line#DEVICE_NAME=}"
                        fi
                        ;;
                    ---) in_pick=0 ;;
                esac
            done < <(probe_vulkan_gpus)
            printf 'info: auto-selected Vulkan GPU %s (%s pci=%s monitors=%s; headless preferred)\n' \
                "$picked" "$picked_name" "$picked_pci" "${picked_monitors:-?}" >&2
            printf '%s\n' "$picked"
            ;;
        *)
            printf '%s\n' "$main_gpu"
            ;;
    esac
}

gpu_free_mib() {
    local target="$1"
    local idx="" free_bytes=""
    while IFS= read -r line; do
        case "$line" in
            GPU_INDEX=*) idx="${line#GPU_INDEX=}" ;;
            FREE_BYTES=*)
                if [ "$idx" = "$target" ]; then
                    free_bytes="${line#FREE_BYTES=}"
                    break
                fi
                ;;
            ---) idx="" ;;
        esac
    done < <(probe_vulkan_gpus)
    if [ -z "$free_bytes" ]; then
        return 1
    fi
    printf '%s\n' $((free_bytes / 1024 / 1024))
}

compute_parallel_slots() {
    local gpu_index="$1"
    local free_mib model_mib kv_mib slots

    if [ -z "$model_gguf" ] || [ ! -f "$model_gguf" ]; then
        printf 'warning: LLAMAFILE_MODEL_GGUF missing; parallel reserve=%s\n' "$parallel_reserve" >&2
        printf '%s\n' "$parallel_reserve"
        return
    fi

    if ! free_mib="$(gpu_free_mib "$gpu_index")"; then
        printf 'warning: could not read VRAM for GPU %s; parallel reserve=%s\n' "$gpu_index" "$parallel_reserve" >&2
        printf '%s\n' "$parallel_reserve"
        return
    fi

    model_mib=$(( $(stat -c '%s' "$model_gguf") / 1024 / 1024 ))
    if [ -n "${LLAMAFILE_KV_MIB_PER_SLOT:-}" ]; then
        kv_mib="$LLAMAFILE_KV_MIB_PER_SLOT"
    else
        kv_mib=$(( (ctx * model_mib * 3) / (8192 * 4) ))
        if [ "$kv_mib" -lt 64 ]; then
            kv_mib=64
        fi
    fi

    slots=$(( (free_mib - margin_mib - model_mib) / kv_mib ))
    if [ "$slots" -lt 1 ]; then
        slots=1
    fi
    if [ -n "$parallel_max" ] && [ "$parallel_max" -gt 0 ] && [ "$slots" -gt "$parallel_max" ]; then
        slots="$parallel_max"
    fi

    printf 'info: VRAM free=%sMiB model=%sMiB kv/slot=%sMiB -> %s slots\n' \
        "$free_mib" "$model_mib" "$kv_mib" "$slots" >&2
    printf '%s\n' "$slots"
}

resolved_gpu="$(resolve_main_gpu)"

if [ "$parallel" = "auto" ] || [ -z "$parallel" ]; then
    resolved_parallel="$(compute_parallel_slots "$resolved_gpu")"
else
    resolved_parallel="$parallel"
fi

printf 'LLAMAFILE_MAIN_GPU=%s\n' "$resolved_gpu"
printf 'LLAMA_ARG_MAIN_GPU=%s\n' "$resolved_gpu"
printf 'LLAMA_ARG_N_PARALLEL=%s\n' "$resolved_parallel"
printf 'LLAMA_ARG_CTX_SIZE=%s\n' "$ctx"
printf 'LLAMA_ARG_SPLIT_MODE=%s\n' "$split_mode"

if [ -n "${LLAMAFILE_TENSOR_SPLIT:-}" ]; then
    printf 'LLAMA_ARG_TENSOR_SPLIT=%s\n' "$LLAMAFILE_TENSOR_SPLIT"
fi