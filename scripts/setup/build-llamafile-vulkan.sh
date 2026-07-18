#!/usr/bin/env bash
# Build ggml-vulkan.so from projects/llamafile/ (upstream llamafile/vulkan.sh).
# Stages the DSO where llamafile's runtime loader searches for it:
#   1. projects/llamafile/o/llamafile/ggml-vulkan.so  (next to engine / tests)
#   2. ~/.llamafile/v/<version>/ggml-vulkan.so          (versioned app dir)
#   3. ~/ggml-vulkan.so                                 (home alternate path)
#
# Requires Vulkan dev packages (glslc, spirv-headers, libvulkan-dev).
# Run: sudo bash scripts/setup/install-vulkan-dev.sh
#
# Usage:
#   build-llamafile-vulkan.sh [--clean] [--force-engine]
set -euo pipefail

CLEAN=0
FORCE_ENGINE=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --clean) CLEAN=1; shift ;;
        --force-engine) FORCE_ENGINE=1; shift ;;
        -h|--help)
            cat >&2 <<'EOF'
Usage: build-llamafile-vulkan.sh [--clean] [--force-engine]

  --clean         Remove cached ~/.cache/llamafile-vulkan-build before building
  --force-engine  Rebuild the llamafile CPU engine even if already present
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
LLAMAFILE_DIR="$PROJECT_ROOT/projects/llamafile"
ENGINE_DIR="$LLAMAFILE_DIR/o/llamafile"
DSO_NAME="ggml-vulkan.so"
VERSION_H="$LLAMAFILE_DIR/llamafile/version.h"

require_cmd() {
    if ! command -v "$1" ; then
        printf 'error: %s not found\n' "$1" >&2
        return 1
    fi
}

# vulkan.sh compiles host-native tools (vulkan-shaders-gen) and a host DSO.
# llamafile_gpu_env_init() forces the system glibc toolchain (see lib/).

printf '=== Checking Vulkan build prerequisites ===\n'
prereq_ok=1
if [ ! -x "$CXX" ]; then
    printf 'error: C++ compiler not found at %s\n' "$CXX" >&2
    printf 'hint: sudo apt-get install -y g++\n' >&2
    prereq_ok=0
fi
require_cmd glslc || prereq_ok=0

vulkan_pkg_ok=0
if pkg-config --exists vulkan; then
    vulkan_pkg_ok=1
fi
if [ "$vulkan_pkg_ok" -eq 0 ] && \
        [ ! -f /usr/include/vulkan/vulkan.h ] && \
        [ ! -f /usr/local/include/vulkan/vulkan.h ]; then
    printf 'error: Vulkan headers not found (libvulkan-dev)\n' >&2
    prereq_ok=0
fi

spirv_ok=0
for candidate in \
    /usr/include/spirv/unified1/spirv.hpp \
    /usr/include/spirv-headers/spirv.hpp \
    /usr/include/spirv.hpp
do
    if [ -f "$candidate" ]; then
        spirv_ok=1
        break
    fi
done
if [ "$spirv_ok" -eq 0 ]; then
    printf 'error: SPIR-V headers not found (spirv-headers package)\n' >&2
    prereq_ok=0
fi

if [ "$prereq_ok" -eq 0 ]; then
    cat >&2 <<'EOF'
hint: install dev packages (needs sudo):
  sudo bash scripts/setup/install-vulkan-dev.sh
EOF
    exit 1
fi

printf '  glslc: %s\n' "$(command -v glslc)"
printf '  CC:    %s\n' "$CC"
printf '  CXX:   %s\n' "$CXX"
printf '\n'

# Drop stale musl-linked artifacts from a prior build that used .boot-linux g++.
VULKAN_CACHE="${HOME}/.cache/llamafile-vulkan-build"
STALE_GEN="${VULKAN_CACHE}/vulkan-shaders-gen"
if [ -f "$STALE_GEN" ] && file -b "$STALE_GEN" | grep -q 'ld-musl'; then
    printf 'Removing stale musl-linked Vulkan cache (wrong toolchain): %s\n' "$VULKAN_CACHE"
    rm -rf "$VULKAN_CACHE"
fi

engine_args=()
if [ "$FORCE_ENGINE" -eq 1 ]; then
    engine_args+=(--force)
fi
bash "$SCRIPT_DIR/build-llamafile-engine.sh" "${engine_args[@]}"

if [ ! -f "$VERSION_H" ]; then
    printf 'error: version header not found: %s\n' "$VERSION_H" >&2
    exit 1
fi
read -r LLAMAFILE_MAJOR LLAMAFILE_MINOR LLAMAFILE_PATCH < <(
    awk '
        /#define LLAMAFILE_MAJOR / { major=$3 }
        /#define LLAMAFILE_MINOR / { minor=$3 }
        /#define LLAMAFILE_PATCH / { patch=$3 }
        END { printf "%s %s %s\n", major, minor, patch }
    ' "$VERSION_H"
)
APP_DSO_DIR="${HOME}/.llamafile/v/${LLAMAFILE_MAJOR}.${LLAMAFILE_MINOR}.${LLAMAFILE_PATCH}"
STAGE_DSO="$ENGINE_DIR/$DSO_NAME"

vulkan_args=()
if [ "$CLEAN" -eq 1 ]; then
    vulkan_args+=(--clean)
fi
vulkan_args+=(--output "$STAGE_DSO")

printf '=== Building %s via projects/llamafile/llamafile/vulkan.sh ===\n' "$DSO_NAME"
cd "$LLAMAFILE_DIR"
LLAMA_CPP_DIR="$LLAMAFILE_DIR/llama.cpp"
GGML_VERSION_MAJOR="$(grep 'set(GGML_VERSION_MAJOR' "$LLAMA_CPP_DIR/ggml/CMakeLists.txt" | sed 's/[^0-9]*//g')"
GGML_VERSION_MINOR="$(grep 'set(GGML_VERSION_MINOR' "$LLAMA_CPP_DIR/ggml/CMakeLists.txt" | sed 's/[^0-9]*//g')"
GGML_VERSION_PATCH="$(grep 'set(GGML_VERSION_PATCH' "$LLAMA_CPP_DIR/ggml/CMakeLists.txt" | sed 's/[^0-9]*//g')"
export GGML_VERSION="${GGML_VERSION_MAJOR}.${GGML_VERSION_MINOR}.${GGML_VERSION_PATCH}"
commit_file="$(mktemp)"
if (cd "$LLAMA_CPP_DIR/ggml" && git rev-parse --short HEAD >"$commit_file"); then
    export GGML_COMMIT="$(cat "$commit_file")"
else
    export GGML_COMMIT="unknown"
fi
rm -f "$commit_file"
bash llamafile/vulkan.sh "${vulkan_args[@]}"

if [ ! -f "$STAGE_DSO" ]; then
    printf 'error: build did not produce %s\n' "$STAGE_DSO" >&2
    exit 1
fi

mkdir -p "$APP_DSO_DIR"
cp -f "$STAGE_DSO" "$APP_DSO_DIR/$DSO_NAME"
cp -f "$STAGE_DSO" "${HOME}/$DSO_NAME"

# cosmo_dlopen() needs a glibc-linked ~/.cosmo/dlopen-helper.
ensure_cosmo_dlopen_helper

printf '================================================================\n'
printf ' VULKAN DSO BUILD SUCCESSFUL\n'
printf ' Staged:\n'
printf '   %s\n' "$STAGE_DSO"
printf '   %s/%s\n' "$APP_DSO_DIR" "$DSO_NAME"
printf '   %s/%s\n' "$HOME" "$DSO_NAME"
ls -lh "$STAGE_DSO"
printf '================================================================\n'