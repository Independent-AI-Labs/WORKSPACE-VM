#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Playwright browsers into .boot-linux/playwright-browsers/
# Downloads chromium and chrome binaries. Does NOT install system deps (no sudo).
# System deps must be installed separately via 'sudo make init'.

_SELF="${BASH_SOURCE[0]}"
if [ -n "${SHG_SCRIPT_PATH:-}" ]; then _SELF="$SHG_SCRIPT_PATH"; fi
SCRIPT_DIR="$(cd "$(dirname "$_SELF")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"
BROWSERS_DIR="${BOOT_DIR}/playwright-browsers"
PLAYWRIGHT="${BIN_DIR}/playwright"

# Containment: interpreters + tool envs live inside the boot dir, never in
# $HOME/.local/share/uv (no unsanctioned HOME/system resources)
export UV_PYTHON_INSTALL_DIR="${BOOT_DIR}/python"
export UV_TOOL_DIR="${BOOT_DIR}/uv-tools"

log_info()    { echo "  $1" >&2; }
log_warn()    { echo "  ⚠ $1" >&2; }
log_error()   { echo "  ERROR: $1" >&2; }
log_success() { echo "  ✓ $1" >&2; }

# Install the playwright CLI as a boot-contained uv tool (never from .venv)
if [[ ! -x "$PLAYWRIGHT" ]]; then
    UV_CMD="${PROJECT_ROOT}/projects/CI/.boot-linux/bin/uv"
    if [[ ! -x "$UV_CMD" ]]; then
        log_error "uv not found at $UV_CMD. Run 'make core' first."
        exit 1
    fi
    if [[ ! -w "$BIN_DIR" ]]; then
        log_error "$BIN_DIR not writable -- boot dir is root-locked; run elevated: sudo make core"
        exit 1
    fi
    log_info "Installing playwright CLI into $BIN_DIR via uv tool..."
    UV_TOOL_BIN_DIR="$BIN_DIR" "$UV_CMD" tool install playwright --force
fi

# Set browsers path - no ~/.cache, everything in .boot-linux
export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"

# Check if already installed with correct version
# playwright install --dry-run shows "Install location: ...chromium-NNN" only when
# the expected version is missing or outdated. If no such line, we're up to date.
if [[ -d "$BROWSERS_DIR" ]] && ! "$PLAYWRIGHT" install --dry-run chromium chrome 2>&1 | grep -q 'Install location:.*chromium-[0-9]'; then
    _pw_err="$(mktemp)"
    EXISTING=$("$PLAYWRIGHT" -version 2>"$_pw_err") || _pw_rc=$?
    if [[ ${_pw_rc:-0} -ne 0 ]]; then
        echo "[bootstrap-playwright] playwright version check failed: $(cat "$_pw_err")" >&2
        EXISTING="unknown"
    fi
    rm -f "$_pw_err"
    log_success "Playwright browsers already installed and up to date ($EXISTING)"
    log_success "  Path: $BROWSERS_DIR"
    exit 0
fi

# Check for key system dependencies BEFORE downloading
MISSING_LIBS=()
for lib in libnss3 libgbm1 libatk-bridge2.0-0t64 libatk-bridge2.0-0; do
    if ! dpkg -s "${lib}" ; then
        # Only mark as missing if no variant of the family is installed
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
    log_warn "Missing system libraries for Playwright: ${MISSING_LIBS[*]}"
    log_warn "Browsers will be downloaded but may not work until you run:"
    log_warn "  make init"
    echo "" >&2
fi

# Download browsers (no --with-deps - never trigger sudo)
log_info "Downloading Playwright browsers to $BROWSERS_DIR..."
mkdir -p "$BROWSERS_DIR"

if "$PLAYWRIGHT" install chromium chrome 2>&1; then
    log_success "Playwright browsers downloaded"
else
    log_error "Playwright browser download failed"
    exit 1
fi

# Verify chromium is operational (only if system deps are present)
if [[ ${#MISSING_LIBS[@]} -eq 0 ]]; then
    log_info "Verifying chromium..."
    VERIFY_IMG="/tmp/playwright-verify-$$.png"
    if timeout 30 "$PLAYWRIGHT" screenshot --browser chromium "data:text/html,<h1>AMI</h1>" "$VERIFY_IMG" 2>&1; then
        rm -f "$VERIFY_IMG"
        log_success "Chromium operational"
    else
        rm -f "$VERIFY_IMG"
        log_warn "Chromium verification failed - browser may need system deps"
        log_warn "Run: make init"
    fi
else
    log_warn "Skipping browser verification - system deps missing"
    log_warn "Run: make init"
fi

log_success "Playwright bootstrap complete"
log_info "  Browsers: $BROWSERS_DIR"
log_info "  Installed: chromium, chrome"
