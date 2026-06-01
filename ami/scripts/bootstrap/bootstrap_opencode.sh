#!/usr/bin/env bash
set -euo pipefail
OP="bootstrap_opencode"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BOOT_DIR="${BOOT_LINUX_DIR:-${AMI_ROOT}/.boot-linux}"

NPM="${BOOT_DIR}/bin/npm"
if [[ ! -x "$NPM" ]]; then
    echo "[${OP}] hermetic npm not found at ${NPM} — run make pre-req first"
    exit 1
fi

echo "[${OP}] Installing opencode-ai into .venv..."
"$NPM" install --prefix "${AMI_ROOT}/.venv" opencode-ai@latest

OPN_BIN="${AMI_ROOT}/.venv/node_modules/.bin/opencode"
if [[ -x "$OPN_BIN" ]]; then
    ln -sf "../../.venv/node_modules/.bin/opencode" "${BOOT_DIR}/bin/opencode"
    echo "[${OP}] opencode-ai $("$OPN_BIN" --version) installed → .boot-linux/bin/opencode"
else
    echo "[${OP}] opencode-ai installed but binary not found at ${OPN_BIN}"
    exit 1
fi
