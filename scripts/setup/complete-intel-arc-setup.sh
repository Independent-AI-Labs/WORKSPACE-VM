#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "========================================================================="
echo " INTEL ARC A770 UNIFIED SYSTEM PROVISIONING SCRIPT "
echo "========================================================================="

# Cache sudo credentials immediately to prevent pipeline password hangs later
echo "Checking administrative privileges..."
sudo true
echo "Password cached successfully. Starting installation pipeline..."
echo ""

echo "=== Step 1: Cleaning up broken repository configs ==="
sudo rm -f /etc/apt/sources.list.d/intel-gpu-noble.list
sudo rm -f /etc/apt/sources.list.d/oneAPI.list

echo "=== Step 2: Provisioning Repository Security Keys ==="
# Add Intel Graphics Key
wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg -yes -dearmor | sudo tee /usr/share/keyrings/intel-graphics.gpg > /dev/null

# Add Intel oneAPI Key
wget -qO - https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg -yes -dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null

echo "=== Step 3: Registering Official Repositories ==="
# 1. Intel Graphics Kobuk PPA for Ubuntu 24.04 (Noble)
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:kobuk-team/intel-graphics

# 2. Intel oneAPI Toolchains
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list

# Synchronize package maps
sudo apt-get update

echo "=== Step 4: Installing Intel Graphics Runtime Layer (Compute & Media) ==="
sudo apt-get install -y \
    libze-intel-gpu1 \
    libze1 \
    intel-metrics-discovery \
    intel-metrics-library \
    intel-opencl-icd \
    clinfo \
    intel-gsc \
    intel-media-va-driver-non-free \
    libmfx-gen1 \
    libvpl2 \
    va-driver-all \
    vainfo \
    xpu-smi

echo "=== Step 5: Installing Intel oneAPI Toolkit & SYCL Compiler Elements ==="
sudo apt-get install -y \
    intel-oneapi-compiler-dpcpp-cpp \
    intel-oneapi-mkl \
    intel-oneapi-mkl-devel

sudo apt-get update && sudo apt-get install -y libssl-dev

echo "=== Step 6: Configuring Hardware User Group Matrices ==="
sudo gpasswd -a "${USER}" render
sudo gpasswd -a "${USER}" video

echo "========================================================================="
echo " ALL INTEL COMPUTE AND DRIVER STACKS PROVISIONED SUCCESSFULLY! "
echo "========================================================================="
echo "To initialize the kernel groups inside your current shell execution block:"
echo "  newgrp render"
echo ""
echo "Verify your system setup status by querying the environment:"
echo "  clinfo | grep \"Device Name\""
echo "  vainfo | grep -i intel"
echo "  xpu-smi stats"
echo "========================================================================="
