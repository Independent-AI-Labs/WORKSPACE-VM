#!/usr/bin/env bash
# Build opencode from source (projects/opencode) into a single Linux x64 binary.
# Leaves the npm-installed 'oc' release untouched.
set -euo pipefail

_SELF="${BASH_SOURCE[0]}"
if [ -n "${SHG_SCRIPT_PATH:-}" ]; then _SELF="$SHG_SCRIPT_PATH"; fi
SCRIPT_DIR="$(cd "$(dirname "$_SELF")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BUN_VERSION="1.3.14"
BUN_BIN="${HOME}/.bun/bin/bun"
OC_DIR="${PROJECT_ROOT}/projects/opencode"
OC_PKG_DIR="${OC_DIR}/packages/opencode"
DIST_BIN="${OC_PKG_DIR}/dist/opencode-linux-x64/bin/opencode"

_bun_ver=""
if [ -x "$BUN_BIN" ]; then
    _raw="$("$BUN_BIN" --version)"
    _bun_ver="$(printf '%s\n' "$_raw" | sed -n '1p')"
fi

if [ "$BUN_VERSION" != "${_bun_ver:-}" ]; then
    echo "[build-opencode] bootstrapping bun ${BUN_VERSION} ..."
    bash "${PROJECT_ROOT}/workspace/scripts/bootstrap/bootstrap_bun.sh"
    _raw="$("$BUN_BIN" --version)"
    _bun_ver="$(printf '%s\n' "$_raw" | sed -n '1p')"
    if [ "$BUN_VERSION" != "$_bun_ver" ]; then
        echo "[build-opencode] ERROR: bun version mismatch after bootstrap (got ${_bun_ver})" >&2
        exit 1
    fi
fi

if [ ! -d "$OC_DIR" ]; then
    echo "[build-opencode] ERROR: opencode source not found at ${OC_DIR}" >&2
    echo "[build-opencode]        Run: make ensure-repos" >&2
    exit 1
fi

_built_version="$(
    OPENCODE_PACKAGE_PATH="$OC_PKG_DIR/package.json" "$BUN_BIN" -e '
        const packagePath = Bun.env.OPENCODE_PACKAGE_PATH
        if (!packagePath) throw new Error("OPENCODE_PACKAGE_PATH is required")
        const packageJson = await Bun.file(packagePath).json()
        if (typeof packageJson.version !== "string" || packageJson.version.length === 0) {
            throw new Error(`package version missing in ${packagePath}`)
        }
        console.log(packageJson.version)
    '
)"
if [ -z "$_built_version" ]; then
    echo "[build-opencode] ERROR: package version is empty" >&2
    exit 1
fi

# Match the npm release database and embed the package's declared version.
export OPENCODE_CHANNEL="latest"
export OPENCODE_VERSION="$_built_version"
echo "[build-opencode] using opencode ${OPENCODE_VERSION} on ${OPENCODE_CHANNEL} channel"

if ! grep -q 'if \[\[ -f ~/.bashrc \]\]; then source ~/.bashrc; fi' "$OC_DIR/packages/core/src/shell.ts"; then
    echo "[build-opencode] WARNING: guard-compliant bash wrapper not detected in shell.ts" >&2
fi

export PATH="${HOME}/.bun/bin:${PATH}"

echo "[build-opencode] installing dependencies in ${OC_DIR} ..."
cd "$OC_DIR"
if ! bun install; then
    echo "[build-opencode] ERROR: bun install failed" >&2
    exit 1
fi

echo "[build-opencode] building opencode (single target) ..."
cd "$OC_PKG_DIR"
if ! bun run script/build.ts --single; then
    echo "[build-opencode] ERROR: build failed" >&2
    exit 1
fi

if [ ! -x "$DIST_BIN" ]; then
    echo "[build-opencode] ERROR: binary not found at ${DIST_BIN}" >&2
    exit 1
fi

_raw="$("$DIST_BIN" --version)"
_reported_version="$(printf '%s\n' "$_raw" | sed -n '1p')"
echo "[build-opencode] built opencode ${_reported_version} at ${DIST_BIN}"
