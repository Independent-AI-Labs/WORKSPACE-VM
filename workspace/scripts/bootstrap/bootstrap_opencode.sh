#!/usr/bin/env bash
set -euo pipefail
OP="bootstrap_opencode"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BOOT_DIR="${BOOT_LINUX_DIR:-${AMI_ROOT}/.boot-linux}"

NPM="${BOOT_DIR}/bin/npm"
if [[ ! -x "$NPM" ]]; then
    echo "[${OP}] hermetic npm not found at ${NPM} - run make pre-req first"
    exit 1
fi

export PATH="${BOOT_DIR}/bin:${PATH}"

echo "[${OP}] Installing opencode-ai into .venv..."
_npm_rc=0
npm install -prefix "${AMI_ROOT}/.venv" opencode-ai@latest || _npm_rc=$?
if [[ $_npm_rc -ne 0 ]]; then
    echo "[${OP}] npm install failed (rc=${_npm_rc}), retrying once..."
    sleep 2
    _npm_rc=0
    npm install -prefix "${AMI_ROOT}/.venv" opencode-ai@latest || _npm_rc=$?
    if [[ $_npm_rc -ne 0 ]]; then
        echo "[${OP}] ERROR: npm install failed after retry (rc=${_npm_rc})"
        exit 1
    fi
    echo "[${OP}] npm install succeeded on retry"
fi

OPN_BIN="${AMI_ROOT}/.venv/node_modules/.bin/opencode"
if [[ -x "$OPN_BIN" ]]; then
    ln -sf "../../.venv/node_modules/.bin/opencode" "${BOOT_DIR}/bin/opencode"
    echo "[${OP}] opencode-ai $("$OPN_BIN" -version) installed → .boot-linux/bin/opencode"
else
    echo "[${OP}] opencode-ai installed but binary not found at ${OPN_BIN}"
    exit 1
fi
