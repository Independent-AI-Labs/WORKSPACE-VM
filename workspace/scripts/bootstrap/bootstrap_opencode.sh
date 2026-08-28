#!/usr/bin/env bash
set -euo pipefail
SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
case "$SCRIPT_SOURCE" in
    /proc/self/fd/*) SCRIPT_SOURCE="${SHG_SCRIPT_PATH:-$SCRIPT_SOURCE}" ;;
esac
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
AMI_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BOOT_DIR="${BOOT_LINUX_DIR:-${AMI_ROOT}/.boot-linux}"
BOOT_BIN="${BOOT_DIR}/bin"
NPM="${BOOT_BIN}/npm"

if [[ ! -w "$BOOT_BIN" ]]; then
    echo "ERROR: ${BOOT_BIN} not writable (root-locked). Run: sudo make update-oc" >&2
    exit 1
fi

if [[ ! -x "$NPM" ]]; then
    echo "ERROR: npm not found at ${NPM}" >&2
    exit 1
fi

PATH="${BOOT_BIN}:${PATH}" "$NPM" install --prefix "$BOOT_DIR" opencode-ai@latest
ln -sfn ../node_modules/.bin/opencode "${BOOT_BIN}/opencode"

if [[ ! -x "${BOOT_BIN}/opencode" ]]; then
    echo "ERROR: opencode binary not found after install" >&2
    exit 1
fi

echo "opencode $(PATH="${BOOT_BIN}:${PATH}" "${BOOT_BIN}/opencode" --version)"
