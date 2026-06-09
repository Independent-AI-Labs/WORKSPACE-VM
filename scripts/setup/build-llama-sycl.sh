#!/usr/bin/env bash
# Build llama.cpp with Intel oneAPI SYCL backend (Arc A770, Flex, Max)
# Persists build to projects/llama.cpp/build-sycl/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LLAMA_DIR="$PROJECT_ROOT/projects/llama.cpp"
BUILD_DIR="$LLAMA_DIR/build-sycl"
ONEAPI_VARS="/opt/intel/oneapi/setvars.sh"

echo "=== Step 1: Checking oneAPI Environment ==="
if [ ! -f "$ONEAPI_VARS" ]; then
    echo "ERROR: Intel oneAPI toolkit not found at $ONEAPI_VARS."
    echo "Install with: sudo bash $SCRIPT_DIR/install-oneapi-dev.sh"
    exit 1
fi

echo "Sourcing Intel environment..."
set +u
source "$ONEAPI_VARS" --force || { echo "ERROR: failed to source $ONEAPI_VARS" >&2; exit 1; }
set -u

echo "=== Step 2: Preparing llama.cpp Source ==="
if [ ! -d "$LLAMA_DIR" ]; then
    echo "Cloning llama.cpp..."
    git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
else
    echo "llama.cpp exists, skipping clone"
fi

echo "=== Step 3: Configuring CMake (SYCL) ==="
cd "$LLAMA_DIR"
rm -rf "$BUILD_DIR"
cmake -B "$BUILD_DIR" \
    -DGGML_SYCL=ON \
    -DLLAMA_OPENSSL=ON \
    -DCMAKE_C_COMPILER=icx \
    -DCMAKE_CXX_COMPILER=icpx \
    -DCMAKE_C_FLAGS="-fuse-ld=/usr/bin/ld" \
    -DCMAKE_CXX_FLAGS="-fuse-ld=/usr/bin/ld" \
    -DCMAKE_BUILD_TYPE=Release

echo "=== Step 4: Building ==="
cmake --build "$BUILD_DIR" --config Release -j"$(nproc)"

echo "================================================================"
echo " BUILD SUCCESSFUL! "
echo " Binary: $BUILD_DIR/bin/llama-server"
echo "================================================================"
_dev_out=""
if "$BUILD_DIR/bin/llama-ls-sycl-device" &>/dev/null; then
    _dev_out="$("$BUILD_DIR/bin/llama-ls-sycl-device" 2>&1)"
elif "$BUILD_DIR/bin/ls-sycl-device" &>/dev/null; then
    _dev_out="$("$BUILD_DIR/bin/ls-sycl-device" 2>&1)"
fi
if [[ -n "$_dev_out" ]]; then
    printf '%s\n' "$_dev_out"
fi
