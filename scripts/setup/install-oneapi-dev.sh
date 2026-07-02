#!/usr/bin/env bash
set -e

echo "========================================================================="
echo " INTEL ONEAPI COMPILER & MKL INSTALL "
echo "========================================================================="

echo "Checking administrative privileges..."
sudo true
echo ""

echo "=== Step 1: Adding Intel oneAPI Repository ==="
sudo rm -f /etc/apt/sources.list.d/oneAPI.list
wget -qO - https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg -yes -dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list
sudo apt-get update

echo "=== Step 2: Installing oneAPI DPC++ Compiler & MKL ==="
sudo apt-get install -y \
    intel-oneapi-compiler-dpcpp-cpp \
    intel-oneapi-mkl \
    intel-oneapi-mkl-devel

sudo apt-get update && sudo apt-get install -y libssl-dev

echo "========================================================================="
echo " INTEL ONEAPI INSTALL COMPLETE "
echo "========================================================================="
echo "Verify with: ls /opt/intel/oneapi/"
echo "========================================================================="
