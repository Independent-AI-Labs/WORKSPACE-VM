#!/usr/bin/env bash
# Bootstrap Bun (oven-sh) into ~/.bun for opencode source builds.
set -euo pipefail

_SELF="${BASH_SOURCE[0]}"
if [ -n "${SHG_SCRIPT_PATH:-}" ]; then _SELF="$SHG_SCRIPT_PATH"; fi
SCRIPT_DIR="$(cd "$(dirname "$_SELF")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

BUN_VERSION="1.3.14"
BUN_INSTALL="${HOME}/.bun"
BUN_BIN="${BUN_INSTALL}/bin/bun"

_bun_ver=""
if [ -x "$BUN_BIN" ]; then
    _raw="$("$BUN_BIN" --version)"
    _bun_ver="$(printf '%s\n' "$_raw" | sed -n '1p')"
fi

if [ "$BUN_VERSION" = "${_bun_ver:-}" ]; then
    echo "[bootstrap_bun] bun ${BUN_VERSION} already installed at ${BUN_BIN}"
    exit 0
fi

if [ -n "${_bun_ver:-}" ]; then
    echo "[bootstrap_bun] replacing bun ${_bun_ver} with ${BUN_VERSION}"
else
    echo "[bootstrap_bun] installing bun ${BUN_VERSION} into ${BUN_INSTALL}"
fi

mkdir -p "$BUN_INSTALL/bin"

TMP_DIR="$(mktemp -d)"
BUN_ZIP="${TMP_DIR}/bun-linux-x64.zip"
URL="https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-x64.zip"

echo "[bootstrap_bun] downloading ${URL} ..."
if ! curl -fsSL -o "$BUN_ZIP" "$URL"; then
    echo "[bootstrap_bun] ERROR: download failed" >&2
    rm -rf "$TMP_DIR"
    exit 1
fi

_extract_dir="${TMP_DIR}/extract"
mkdir -p "$_extract_dir"

if ! unzip -o "$BUN_ZIP" -d "$_extract_dir"; then
    echo "[bootstrap_bun] ERROR: unzip failed" >&2
    rm -rf "$TMP_DIR"
    exit 1
fi

_bun_src=""
while IFS= read -r _candidate; do
    if [ -x "$_candidate" ]; then
        _bun_src="$_candidate"
        break
    fi
done < <(find "$TMP_DIR" -type f -name bun)

if [ -z "$_bun_src" ]; then
    echo "[bootstrap_bun] ERROR: extracted bun binary not found" >&2
    rm -rf "$TMP_DIR"
    exit 1
fi

mv "$_bun_src" "$BUN_BIN"
chmod +x "$BUN_BIN"
rm -rf "$TMP_DIR"

_raw="$("$BUN_BIN" --version)"
_installed="$(printf '%s\n' "$_raw" | sed -n '1p')"
if [ "$BUN_VERSION" != "$_installed" ]; then
    echo "[bootstrap_bun] ERROR: version mismatch (got ${_installed})" >&2
    exit 1
fi

echo "[bootstrap_bun] bun ${_installed} installed at ${BUN_BIN}"
