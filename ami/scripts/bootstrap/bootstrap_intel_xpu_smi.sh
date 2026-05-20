#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo "=== Intel XPU-SMI Bootstrap ==="

if command -v xpu-smi &>/dev/null; then
    xpu_ver="$(xpu-smi -v 2>&1)"
    xpu_ver="${xpu_ver%%$'\n'*}"
    echo "xpu-smi already installed: $xpu_ver"
    exit 0
fi

echo "Installing xpu-smi..."

sudo apt-get update
sudo apt-get install -y \
    libze-intel-gpu1 \
    libze1 \
    intel-metrics-discovery \
    intel-metrics-library \
    intel-opencl-icd \
    xpu-smi

echo "Verifying installation..."
if command -v xpu-smi &>/dev/null; then
    xpu_ver="$(xpu-smi -v 2>&1)"
    xpu_ver="${xpu_ver%%$'\n'*}"
    echo "xpu-smi installed: $xpu_ver"
else
    echo "ERROR: xpu-smi command not found after installation"
    exit 1
fi