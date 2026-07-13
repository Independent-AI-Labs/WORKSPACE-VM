#!/usr/bin/env bash
# Run the incremental transcript classifier benchmark against CPU and Vulkan backends.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

MODEL="${MODEL:-minicpm5-1b}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"
TIMEOUT="${TIMEOUT:-3600}"
MAKEFILE="Makefile.llamafile"
LOG_DIR="$REPO_ROOT/docs/benchmarking/llamafile-transcript-classifier/_logs"
mkdir -p "$LOG_DIR"

run_bench() {
    local backend="$1"
    local log_file="$LOG_DIR/bench-${backend}-$(date -u +%Y%m%dT%H%M%SZ).log"
    printf '[%s] starting %s benchmark (log: %s)\n' "$(date -u +%H:%M:%S)" "$backend" "$log_file"
    if ! curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then
        printf 'error: llamafile not healthy at %s before %s run\n' "$BASE_URL" "$backend" >&2
        return 1
    fi
    uv run -m scripts.benchmark.llamafile_transcript_classifier \
        --base-url "$BASE_URL" \
        --backend "$backend" \
        --timeout "$TIMEOUT" \
        2>&1 | tee "$log_file"
    local rc=${PIPESTATUS[0]}
    printf '[%s] %s benchmark finished (exit=%s)\n' "$(date -u +%H:%M:%S)" "$backend" "$rc"
    return "$rc"
}

deploy_backend() {
    local backend="$1"
    printf '[%s] deploying llamafile backend=%s model=%s\n' "$(date -u +%H:%M:%S)" "$backend" "$MODEL"
    make -f "$MAKEFILE" install-llamafile MODEL="$MODEL" GPU="$backend"
    local waited=0
    while ! curl -sf "${BASE_URL}/health" >/dev/null 2>&1; do
        sleep 2
        waited=$((waited + 2))
        if [ "$waited" -ge 120 ]; then
            printf 'error: llamafile not healthy after deploying %s\n' "$backend" >&2
            return 1
        fi
    done
    printf '[%s] %s backend healthy at %s\n' "$(date -u +%H:%M:%S)" "$backend" "$BASE_URL"
}

if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.venv/bin/activate" || exit 1
fi

VULKAN_RC=0
CPU_RC=0

env_file="$HOME/.config/llamafile/llamafile-${MODEL}.env"
current_gpu=""
if [ -f "$env_file" ]; then
    current_gpu="$(grep -E '^LLAMAFILE_GPU=' "$env_file" | cut -d= -f2)"
fi
if [ "$current_gpu" = "vulkan" ]; then
    run_bench vulkan || VULKAN_RC=$?
else
    deploy_backend vulkan
    run_bench vulkan || VULKAN_RC=$?
fi

deploy_backend cpu
run_bench cpu || CPU_RC=$?

deploy_backend vulkan

printf '\n=== BENCHMARK RUN COMPLETE ===\n'
printf 'vulkan exit: %s\n' "$VULKAN_RC"
printf 'cpu exit: %s\n' "$CPU_RC"
printf 'reports: docs/benchmarking/llamafile-transcript-classifier/{vulkan,cpu}/\n'

if [ "$VULKAN_RC" -ne 0 ] || [ "$CPU_RC" -ne 0 ]; then
    exit 2
fi