#!/usr/bin/env bash
# Build llama.cpp with CPU-only backend
# Persists build to projects/llama.cpp/build-cpu/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LLAMA_DIR="$PROJECT_ROOT/projects/llama.cpp"
BUILD_DIR="$LLAMA_DIR/build-cpu"

echo "=== Checking prerequisites ==="
if ! command -v cmake &>/dev/null; then
    echo "ERROR: cmake not found. Install with: sudo apt-get install -y cmake"
    exit 1
fi
cmake_ver="$(cmake --version 2>&1)"
cmake_ver="${cmake_ver%%$'\n'*}"
echo "  cmake: $cmake_ver"
echo ""

echo "=== Step 1: Preparing llama.cpp Source ==="
if [ ! -d "$LLAMA_DIR" ]; then
    echo "Cloning llama.cpp..."
    git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
fi

echo "=== Step 2: Configuring CMake (CPU) ==="
cd "$LLAMA_DIR"
export CC=/usr/bin/gcc
export CXX=/usr/bin/g++
cmake -B "$BUILD_DIR" \
    -DGGML_VULKAN=OFF \
    -DGGML_SYCL=OFF \
    -DGGML_OPENBLAS=ON \
    -DCMAKE_C_COMPILER=/usr/bin/gcc \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
    -DCMAKE_C_FLAGS="-B/usr/bin" \
    -DCMAKE_CXX_FLAGS="-B/usr/bin" \
    -DCMAKE_BUILD_TYPE=Release

echo "=== Step 3: Building ==="
cmake --build "$BUILD_DIR" --config Release -j"$(nproc)"

echo "================================================================"
echo " BUILD SUCCESSFUL! "
echo " Binary: $BUILD_DIR/bin/llama-server"
echo "================================================================"
