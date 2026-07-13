#!/usr/bin/env bash
# Test llamafile Vulkan integration against projects/llamafile/.
#
# Phases:
#   1. gpu_backend_test: probe tests (no GPU; always runs)
#   2. DSO presence: ggml-vulkan.so staged next to engine
#   3. backend_ops_test: numerical consistency vs CPU (needs GPU + DSO)
#   4. runtime probe: llamafile --gpu vulkan loads the DSO
#   5. optional quick check: MODEL=<dir> runs a one-token CLI generation
#
# Usage:
#   test-llamafile-vulkan.sh
#   test-llamafile-vulkan.sh --skip-gpu     # phases 1-2 only
#   MODEL=minicpm5-1b test-llamafile-vulkan.sh
set -euo pipefail

SKIP_GPU=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-gpu) SKIP_GPU=1; shift ;;
        -h|--help)
            cat >&2 <<'EOF'
Usage: test-llamafile-vulkan.sh [--skip-gpu]

  --skip-gpu   Run unit/probe tests only; skip GPU-dependent phases

Environment:
  MODEL        If set (e.g. minicpm5-1b), run a one-token CLI quick check when
               the GGUF is present under models/<MODEL>/
EOF
            exit 0
            ;;
        *)
            printf 'error: unknown argument: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=lib/llamafile-gpu-env.sh
source "$SCRIPT_DIR/lib/llamafile-gpu-env.sh" || exit 1
llamafile_gpu_env_init
ensure_cosmo_dlopen_helper

LLAMAFILE_DIR="$PROJECT_ROOT/projects/llamafile"
COSMO_MAKE="$LLAMAFILE_DIR/.cosmocc/4.0.2/bin/make"
ENGINE="$LLAMAFILE_DIR/o/llamafile/llamafile"
DSO="$LLAMAFILE_DIR/o/llamafile/ggml-vulkan.so"
BACKEND_OPS="$LLAMAFILE_DIR/o/tests/backend_ops_test"
GPU_TEST="$LLAMAFILE_DIR/o/tests/gpu_backend_test"

failures=0
pass() { printf '[PASS] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1" >&2; failures=$((failures + 1)); }

if [ ! -d "$LLAMAFILE_DIR" ]; then
    printf 'error: llamafile source not found at %s\n' "$LLAMAFILE_DIR" >&2
    exit 1
fi
if [ ! -x "$COSMO_MAKE" ]; then
    printf 'error: cosmocc make missing; run: make build-llamafile-engine\n' >&2
    exit 1
fi
if [ ! -x "$ENGINE" ]; then
    printf 'error: llamafile engine missing; run: make build-llamafile-engine\n' >&2
    exit 1
fi

printf '=== Phase 1: gpu_backend_test (probe tests, no GPU) ===\n'
cd "$LLAMAFILE_DIR"
if "$COSMO_MAKE" o//tests/gpu_backend_test.runs; then
    pass "gpu_backend_test"
else
    fail "gpu_backend_test"
fi

printf '\n=== Phase 2: Vulkan DSO presence ===\n'
if [ -f "$DSO" ]; then
    pass "ggml-vulkan.so staged at $DSO"
    ls -lh "$DSO"
else
    fail "ggml-vulkan.so missing at $DSO (run: make build-llamafile-vulkan)"
fi

if [ "$SKIP_GPU" -eq 1 ]; then
    printf '\n--skip-gpu set; skipping GPU runtime tests\n'
    if [ "$failures" -ne 0 ]; then
        exit 1
    fi
    exit 0
fi

if [ ! -f "$DSO" ]; then
    printf '\nCannot run GPU phases without DSO; exiting.\n'
    exit 1
fi

printf '\n=== Phase 3: backend_ops_test (Vulkan numerical consistency) ===\n'
if ! command -v vulkaninfo >/dev/null 2>&1; then
    fail "vulkaninfo not found; install vulkan-tools"
else
    if "$COSMO_MAKE" o//tests/backend_ops_test; then
        pass "backend_ops_test built"
        probe_dir="$(mktemp -d)"
        cp -f "$BACKEND_OPS" "$probe_dir/"
        cp -f "$DSO" "$probe_dir/"
        ops_log="$(mktemp)"
        if (
            cd "$probe_dir"
            ./backend_ops_test test -o MUL_MAT -b Vulkan0
        ) >"$ops_log" 2>&1; then
            if grep -qi 'vulkan backend not available\|no GPU backend loaded' "$ops_log"; then
                fail "backend_ops_test did not load Vulkan (see $ops_log)"
            elif grep -qi 'Backend.*Vulkan0' "$ops_log" || grep -qi 'Vulkan0' "$ops_log"; then
                pass "backend_ops_test MUL_MAT on Vulkan0"
            else
                fail "backend_ops_test ran but Vulkan backend unclear (see $ops_log)"
            fi
        else
            fail "backend_ops_test MUL_MAT on Vulkan0 (see $ops_log)"
        fi
        rm -f "$ops_log"
        rm -rf "$probe_dir"
    else
        fail "backend_ops_test build"
    fi
fi

printf '\n=== Phase 4: llamafile --gpu vulkan runtime probe ===\n'
probe_dir="$(mktemp -d)"
cp -f "$ENGINE" "$probe_dir/llamafile"
cp -f "$DSO" "$probe_dir/ggml-vulkan.so"
chmod +x "$probe_dir/llamafile"
probe_log="$(mktemp)"
if "$probe_dir/llamafile" --verbose --gpu vulkan --version >"$probe_log" 2>&1; then
    if grep -qi "dlopen() isn't supported on this platform" "$probe_log"; then
        fail "cosmo_dlopen broken; rebuild engine/vulkan (llamafile_gpu_env_init)"
    elif grep -qi 'Vulkan GPU support successfully loaded' "$probe_log"; then
        pass "llamafile --gpu vulkan loaded ggml-vulkan.so"
    else
        # --version skips GPU init; probe load with a missing-model argv parse.
        rm -f "$probe_log"
        if ! "$probe_dir/llamafile" --verbose --gpu vulkan -m /nonexistent.gguf 2>"$probe_log"; then
            :
        fi
        if grep -qi 'Vulkan GPU support successfully loaded' "$probe_log"; then
            pass "llamafile --gpu vulkan loaded ggml-vulkan.so"
        elif grep -qi "dlopen() isn't supported" "$probe_log"; then
            fail "cosmo_dlopen broken; rebuild engine/vulkan (llamafile_gpu_env_init)"
        else
            fail "llamafile --gpu vulkan did not load ggml-vulkan.so (see $probe_log)"
        fi
    fi
else
    fail "llamafile --gpu vulkan probe exited non-zero (see $probe_log)"
fi
rm -f "$probe_log"
rm -rf "$probe_dir"

if [ -n "${MODEL:-}" ]; then
    printf '\n=== Phase 5: MODEL quick check (%s) ===\n' "$MODEL"
    model_dir="$PROJECT_ROOT/models/$MODEL"
    gguf=""
    count=0
    while IFS= read -r -d '' f; do
        gguf="$f"
        count=$((count + 1))
    done < <(find "$model_dir" -maxdepth 1 -type f -name '*.gguf' -print0)
    if [ "$count" -ne 1 ] || [ -z "$gguf" ]; then
        fail "expected exactly one .gguf in $model_dir for quick check"
    else
        quick_log="$(mktemp)"
        if "$ENGINE" --gpu vulkan -m "$gguf" -p "Reply with one word: ok" --cli -n 4 \
                >"$quick_log" 2>&1; then
            pass "one-token CLI generation with --gpu vulkan"
        else
            fail "CLI quick check with --gpu vulkan (see $quick_log)"
        fi
        rm -f "$quick_log"
    fi
fi

printf '\n=== test-llamafile-vulkan rollup ===\n'
if [ "$failures" -ne 0 ]; then
    printf '%d phase(s) failed\n' "$failures" >&2
    exit 1
fi
printf 'all phases passed\n'