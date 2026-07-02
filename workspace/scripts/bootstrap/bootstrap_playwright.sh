#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Playwright browsers into .boot-linux/playwright-browsers/
# Downloads chromium and chrome binaries. Does NOT install system deps (no sudo).
# System deps must be installed separately via 'sudo make init'.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BROWSERS_DIR="${BOOT_DIR}/playwright-browsers"
PLAYWRIGHT="${PROJECT_ROOT}/.venv/bin/playwright"

log_info()    { echo "  $1" >&2; }
log_warn()    { echo "  ⚠ $1" >&2; }
log_error()   { echo "  ERROR: $1" >&2; }
log_success() { echo "  ✓ $1" >&2; }

# Check playwright is installed
if [[ ! -x "$PLAYWRIGHT" ]]; then
    log_error "playwright not found at $PLAYWRIGHT"
    log_error "Run 'uv sync' first to install Python dependencies."
    exit 1
fi

# Set browsers path - no ~/.cache, everything in .boot-linux
export PLAYWRIGHT_BROWSERS_PATH="$BROWSERS_DIR"

# Check if already installed with correct version
# playwright install --dry-run shows "Install location: ...chromium-NNN" only when
# the expected version is missing or outdated. If no such line, we're up to date.
if [[ -d "$BROWSERS_DIR" ]] && ! "$PLAYWRIGHT" install --dry-run chromium chrome 2>&1 | grep -q 'Install location:.*chromium-[0-9]'; then
    _pw_err="$(mktemp)"
    EXISTING=$("$PLAYWRIGHT" -version 2>"$_pw_err") || {
        echo "[bootstrap-playwright] playwright version check failed: $(cat "$_pw_err")" >&2
        EXISTING="unknown"
    }
    rm -f "$_pw_err"
    log_success "Playwright browsers already installed and up to date ($EXISTING)"
    log_success "  Path: $BROWSERS_DIR"
    exit 0
fi

# Check for key system dependencies BEFORE downloading
MISSING_LIBS=()
for lib in libnss3 libgbm1 libatk-bridge2.0-0t64 libatk-bridge2.0-0; do
    if ! dpkg -s "${lib}" &>/dev/null 2>&1; then
        # Only mark as missing if no variant of the family is installed
        case "$lib" in
            libatk-bridge2.0-0)
                dpkg -s libatk-bridge2.0-0t64 &>/dev/null 2>&1 && continue ;;
            libatk-bridge2.0-0t64)
                dpkg -s libatk-bridge2.0-0   &>/dev/null 2>&1 && continue ;;
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
