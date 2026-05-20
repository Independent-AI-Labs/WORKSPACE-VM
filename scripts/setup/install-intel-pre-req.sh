#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Step 1: Cleaning up broken repository configuration ==="
sudo rm -f /etc/apt/sources.list.d/intel-gpu-noble.list

echo "=== Step 2: Adding Official Intel Graphics PPA for Ubuntu 24.04 ==="
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:kobuk-team/intel-graphics
sudo apt-get update

echo "=== Step 3: Installing Intel Compute & OpenCL Packages ==="
sudo apt-get install -y \
    libze-intel-gpu1 \
    libze1 \
    intel-metrics-discovery \
    intel-metrics-library \
    intel-opencl-icd \
    clinfo \
    intel-gsc \
    xpu-smi

echo "=== Step 4: Installing Intel Hardware Media Accelerator Packages ==="
sudo apt-get install -y \
    intel-media-va-driver-non-free \
    libmfx-gen1 \
    libvpl2 \
    va-driver-all \
    vainfo

echo "=== Step 5: Configuring User Hardware Permissions ==="
sudo gpasswd -a "${USER}" render
sudo gpasswd -a "${USER}" video

echo "========================================================================="
echo " SETUP COMPLETE! "
echo "========================================================================="
echo "To apply your new user permissions immediately without rebooting, run:"
echo "  newgrp render"
echo ""
echo "Then, you can verify your Arc A770 using these commands:"
echo "  clinfo | grep \"Device Name\""
echo "  vainfo | grep -i intel"
echo "  xpu-smi stats"
echo "========================================================================="
