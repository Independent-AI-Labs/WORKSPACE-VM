#!/usr/bin/env bash
set -e

echo "========================================================================="
echo " VULKAN DEV SDK INSTALL "
echo "========================================================================="

echo "Checking administrative privileges..."
sudo true
echo ""

echo "=== Step 1: Installing Vulkan headers, drivers & shader compiler ==="
sudo apt-get update
sudo apt-get install -y \
    libvulkan-dev \
    mesa-vulkan-drivers \
    libshaderc-dev \
    glslc \
    spirv-headers \
    vulkan-tools

echo "========================================================================="
echo " VULKAN SDK INSTALL COMPLETE "
echo "========================================================================="
dpkg_ver="$(dpkg -l libvulkan-dev 2>&1)"
dpkg_ver="${dpkg_ver##*$'\n'}"
echo "Verify with: $dpkg_ver"
echo "========================================================================="
