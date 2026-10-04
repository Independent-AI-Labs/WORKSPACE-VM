#!/bin/bash
set -euo pipefail

# Bootstrap the WORKSPACE-BROWSER (`wsb`) CLI and its Chromium engine.
#
# Replaces the retired Python-playwright bootstrap: the browser is now a
# native Node/TypeScript project (projects/WORKSPACE-BROWSER) that owns its
# Playwright version and pins the Chromium executable in config. This script
# clones the repo on demand, builds it, downloads Chromium into the boot
# directory, and resolves the executable path.
#
# Does NOT install system deps (no sudo); run 'make init' for those.

_SELF="${BASH_SOURCE[0]}"
if [ -n "${SHG_SCRIPT_PATH:-}" ]; then _SELF="$SHG_SCRIPT_PATH"; fi
SCRIPT_DIR="$(cd "$(dirname "$_SELF")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"
BROWSERS_DIR="${BOOT_DIR}/playwright-browsers"
REPO_DIR="${PROJECT_ROOT}/projects/WORKSPACE-BROWSER"

CI_DIR="${CI_DIR:-/opt/workspace-ci}"
if [[ "$(uname -s)" == "Darwin" ]]; then
    NODE_BIN="${PROJECT_ROOT}/projects/WORKSPACE-CI/.boot-macos/node-env/bin"
else
    NODE_BIN="${CI_DIR}/.boot-linux/node-env/bin"
fi
NODE="${NODE_BIN}/node"
NPM="${NODE_BIN}/npm"

log_info()    { echo "  $1" >&2; }
log_warn()    { echo "  ⚠ $1" >&2; }
log_error()   { echo "  ERROR: $1" >&2; }
log_success() { echo "  ✓ $1" >&2; }

# Checkout boot directories are local developer state, never root-installed.
if [[ "$(id -u)" == "0" ]]; then
    log_error "local browser installation must run as the checkout owner, not root"
    exit 1
fi
if [[ -e "$BOOT_DIR" && ! -O "$BOOT_DIR" ]]; then
    log_error "checkout boot directory is not owned by the current user: $BOOT_DIR"
    exit 1
fi
if ! mkdir -p "$BIN_DIR"; then
    log_error "cannot create checkout boot directory: $BIN_DIR"
    exit 1
fi
if [[ ! -w "$BOOT_DIR" || ! -w "$BIN_DIR" ]]; then
    log_error "checkout boot directory is not writable: $BOOT_DIR"
    exit 1
fi

# Node.js is provisioned by the sealed WORKSPACE-CI artifact ('make core').
if [[ ! -x "$NODE" || ! -x "$NPM" ]]; then
    log_error "node/npm not found at $NODE_BIN. Run 'make core' first."
    exit 1
fi
export PATH="${NODE_BIN}:${PATH}"

# Clone the browser repo on demand (optional workspace clone).
if [[ ! -d "${REPO_DIR}/.git" ]]; then
    log_info "Cloning WORKSPACE-BROWSER..."
    bash "${PROJECT_ROOT}/workspace/scripts/bin/bootstrap-repos" --include workspace-browser
fi

# Contain Chromium under the checkout boot dir, never ~/.cache.
export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"
mkdir -p "$BROWSERS_DIR"

# Check for key system dependencies BEFORE downloading (Linux only).
MISSING_LIBS=()
if [[ "$(uname -s)" != "Darwin" ]]; then
    for lib in libnss3 libgbm1 libatk-bridge2.0-0t64 libatk-bridge2.0-0; do
        if ! dpkg -s "${lib}" ; then
            case "$lib" in
                libatk-bridge2.0-0)
                    dpkg -s libatk-bridge2.0-0t64  && continue ;;
                libatk-bridge2.0-0t64)
                    dpkg -s libatk-bridge2.0-0    && continue ;;
            esac
            MISSING_LIBS+=("$lib")
        fi
    done

    if [[ ${#MISSING_LIBS[@]} -gt 0 ]]; then
        log_warn "Missing system libraries for Chromium: ${MISSING_LIBS[*]}"
        log_warn "The browser may not run until you run: make init"
    fi
fi

# Build the CLI and install its pinned Chromium.
cd "$REPO_DIR"
log_info "Installing npm dependencies..."
"$NPM" ci
log_info "Building wsb..."
"$NPM" run build
log_info "Downloading Chromium into $BROWSERS_DIR..."
"${REPO_DIR}/node_modules/.bin/playwright" install chromium
log_info "Resolving Chromium executable path..."
"$NPM" run setup:browser

# Verify the built CLI answers help.
if ! "$NODE" "${REPO_DIR}/dist/cli/main.js" --help; then
    log_error "wsb build verification failed"
    exit 1
fi
log_success "wsb operational"

if [[ ${#MISSING_LIBS[@]} -gt 0 ]]; then
    log_warn "Chromium may need system deps - run: make init"
fi

log_success "WORKSPACE-BROWSER bootstrap complete"
log_info "  Repo: $REPO_DIR"
log_info "  Browsers: $BROWSERS_DIR"
