#!/usr/bin/env bash
set -euo pipefail
OP="bootstrap_opencode"

if ! command -v npm &>/dev/null; then
    echo "[${OP}] node/npm not found — install Node.js first (make pre-req)"
    exit 1
fi

echo "[${OP}] Installing opencode-ai..."
npm install -g opencode-ai@latest
touch .boot-linux/.opencode-installed
echo "[${OP}] opencode-ai $(opencode --version 2>/dev/null || npx opencode --version) installed"
