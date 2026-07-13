#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
INSTALL_SCRIPT="${PROJECT_ROOT}/scripts/setup/install-intel-pre-req.sh"

echo "=== Intel XPU-SMI Bootstrap ==="

if command -v xpu-smi &>/dev/null; then
    xpu_ver="$(xpu-smi -v 2>&1)"
    xpu_ver="${xpu_ver%%$'\n'*}"
    echo "xpu-smi already installed: $xpu_ver"
    exit 0
fi

if [ ! -f "$INSTALL_SCRIPT" ]; then
    echo "ERROR: install script not found: $INSTALL_SCRIPT" >&2
    exit 1
fi

echo "Delegating to ${INSTALL_SCRIPT} (adds Intel graphics PPA, then installs xpu-smi)..."
sudo bash "$INSTALL_SCRIPT"

echo "Verifying installation..."
if command -v xpu-smi &>/dev/null; then
    xpu_ver="$(xpu-smi -v 2>&1)"
    xpu_ver="${xpu_ver%%$'\n'*}"
    echo "xpu-smi installed: $xpu_ver"
else
    echo "ERROR: xpu-smi command not found after installation" >&2
    exit 1
fi