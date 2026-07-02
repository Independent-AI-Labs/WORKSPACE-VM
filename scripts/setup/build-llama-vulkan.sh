#!/usr/bin/env bash
# Build llama.cpp with Vulkan backend (Intel Arc A770, any GPU with Vulkan)
# Persists build to projects/llama.cpp/build-vulkan/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LLAMA_DIR="$PROJECT_ROOT/projects/llama.cpp"
BUILD_DIR="$LLAMA_DIR/build-vulkan"

echo "=== Checking prerequisites ==="
if ! command -v cmake &>/dev/null; then
    echo "ERROR: cmake not found. Install with: sudo apt-get install -y cmake"
    exit 1
fi
cmake_ver="$(cmake --version 2>&1)"
cmake_ver="${cmake_ver%%$'\n'*}"
echo "  cmake: $cmake_ver"

echo "=== Step 1: Checking Vulkan SDK ==="
if ! dpkg -l libvulkan-dev &>/dev/null; then
    echo "Vulkan headers not found. Install with:"
    echo "  sudo apt-get install -y libvulkan-dev"
    echo ""
    echo "Required packages for Vulkan compute:"
    echo "  libvulkan-dev          - Vulkan headers and libraries"
    echo "  mesa-vulkan-drivers    - Vulkan driver for Intel/AMD"
    echo "  libshaderc1            - SPIR-V shader compilation"
    echo ""
    exit 1
fi

echo "=== Step 2: Preparing llama.cpp Source ==="
if [ ! -d "$LLAMA_DIR" ]; then
    echo "Cloning llama.cpp..."
    git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
else
    echo "llama.cpp exists, skipping clone"
fi

echo "=== Step 3: Configuring CMake (Vulkan) ==="
cd "$LLAMA_DIR"
# Prepend /usr/bin so system ld is found before .boot-linux musl ld
export PATH="/usr/bin:$PATH"
cmake -B "$BUILD_DIR" \
    -DGGML_VULKAN=ON \
    -DGGML_SYCL=OFF \
    -DCMAKE_C_COMPILER=/usr/bin/gcc \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
    -DCMAKE_C_FLAGS="-B/usr/bin" \
    -DCMAKE_CXX_FLAGS="-B/usr/bin" \
    -DVulkan_LIBRARY=/usr/lib/x86_64-linux-gnu/libvulkan.so \
    -DCMAKE_BUILD_TYPE=Release

echo "=== Step 4: Building ==="
cmake --build "$BUILD_DIR" --config Release -j"$(nproc)"

echo "================================================================"
echo " BUILD SUCCESSFUL! "
echo " Binary: $BUILD_DIR/bin/llama-server"
echo "================================================================"
