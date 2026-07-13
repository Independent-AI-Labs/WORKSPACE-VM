#!/usr/bin/env bash
# Build the llamafile CPU engine (fat APE) from projects/llamafile/.
# Output: projects/llamafile/o/llamafile/llamafile
#         projects/llamafile/o/third_party/zipalign/zipalign
#
# Usage:
#   build-llamafile-engine.sh [--force]
set -euo pipefail

FORCE=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --force) FORCE=1; shift ;;
        -h|--help)
            printf 'Usage: build-llamafile-engine.sh [--force]\n'
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
LLAMAFILE_DIR="$PROJECT_ROOT/projects/llamafile"
COSMO_MAKE="$LLAMAFILE_DIR/.cosmocc/4.0.2/bin/make"
ENGINE="$LLAMAFILE_DIR/o/llamafile/llamafile"
ZIPALIGN="$LLAMAFILE_DIR/o/third_party/zipalign/zipalign"

if [ ! -d "$LLAMAFILE_DIR" ]; then
    printf 'error: llamafile source not found at %s\n' "$LLAMAFILE_DIR" >&2
    printf 'hint: clone or sync projects/llamafile first (make ensure-repos)\n' >&2
    exit 1
fi

if [ "$FORCE" -eq 0 ] && [ -x "$ENGINE" ] && [ -x "$ZIPALIGN" ]; then
    printf '✅ llamafile engine already built at %s\n' "$ENGINE"
    printf '   (use --force to rebuild)\n'
    exit 0
fi

printf '=== Step 1: llamafile setup (submodules, cosmocc, patches) ===\n'
cd "$LLAMAFILE_DIR"
if [ ! -x "$COSMO_MAKE" ]; then
    make setup
fi

printf '=== Step 2: Building llamafile engine (fat APE, CPU-only) ===\n'
"$COSMO_MAKE" -j"$(nproc)"

missing=0
for p in "$ENGINE" "$ZIPALIGN"; do
    if [ ! -x "$p" ]; then
        printf 'error: expected executable missing: %s\n' "$p" >&2
        missing=1
    fi
done
if [ "$missing" -ne 0 ]; then
    exit 1
fi

# GPU backends need a glibc dlopen-helper even for a CPU-only engine build.
if [ -f "${HOME}/.cosmo/dlopen-helper.c" ]; then
    ensure_cosmo_dlopen_helper
fi

printf '================================================================\n'
printf ' BUILD SUCCESSFUL\n'
printf ' Engine:   %s\n' "$ENGINE"
printf ' zipalign: %s\n' "$ZIPALIGN"
printf '================================================================\n'