#!/usr/bin/env bash
set -euo pipefail

# moon Bootstrap Script for WORKSPACE-VM
# Downloads moon (moonrepo) binary and installs to .boot-linux/bin
# moon is the workspace task runner / project-graph dep validator.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in ami/scripts/bootstrap/, project root is 3 levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Idempotency: skip if moon is already installed
if [ -x "${BIN_DIR}/moon" ]; then
    log_info "moon already installed at ${BIN_DIR}/moon"
    "${BIN_DIR}/moon" -version
    exit 0
fi

# Create directories
mkdir -p "${BIN_DIR}"

# Detect architecture and OS
RAW_OS=$(uname -s)
RAW_ARCH=$(uname -m)

case "$RAW_OS" in
    Linux*)
        PLATFORM="unknown-linux-gnu"
        ;;
    Darwin*)
        PLATFORM="apple-darwin"
        ;;
    *)
        log_error "Unsupported OS: $RAW_OS"
        exit 1
        ;;
esac

case "$RAW_ARCH" in
    x86_64*|amd64*)
        ARCH="x86_64"
        ;;
    arm64*|aarch64*)
        ARCH="aarch64"
        ;;
    *)
        log_error "Unsupported architecture: $RAW_ARCH"
        exit 1
        ;;
esac

# moon ships as: moon_cli-<arch>-<platform>.tar.xz containing moon + moonx
TARGET="${ARCH}-${PLATFORM}"
ASSET="moon_cli-${TARGET}.tar.xz"
URL_LATEST="https://github.com/moonrepo/moon/releases/latest/download/${ASSET}"

log_info "Downloading moon for ${TARGET}..."

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

cd "$TEMP_DIR"

# Try latest first; on failure resolve the explicit tag and retry.
if ! curl -fLsS "$URL_LATEST" -o "$ASSET"; then
    log_warn "Latest-download URL failed, resolving explicit tag from GitHub API..."
    if ! TAG=$(curl -fsSL https://api.github.com/repos/moonrepo/moon/releases/latest \
        | uv run python -c "import json,sys;print(json.load(sys.stdin)['tag_name'])"); then
        log_error "Failed to resolve latest moon release tag from GitHub API"
        exit 1
    fi
    log_info "Resolved tag: ${TAG}"
    URL_TAG="https://github.com/moonrepo/moon/releases/download/${TAG}/${ASSET}"
    if ! curl -fLsS "$URL_TAG" -o "$ASSET"; then
        log_error "Failed to download moon asset from ${URL_TAG}"
        exit 1
    fi
fi

# Extract
if ! tar -xJf "$ASSET"; then
    log_error "Failed to extract ${ASSET}"
    exit 1
fi

EXTRACTED_DIR="moon_cli-${TARGET}"
if [ ! -f "${EXTRACTED_DIR}/moon" ]; then
    log_error "Could not find moon binary in extracted archive at ${EXTRACTED_DIR}/moon"
    ls -la "${EXTRACTED_DIR}"
    exit 1
fi

# Install moon
chmod +x "${EXTRACTED_DIR}/moon"
cp "${EXTRACTED_DIR}/moon" "${BIN_DIR}/moon"

# Install moonx (sibling launcher) if present
if [ -f "${EXTRACTED_DIR}/moonx" ]; then
    chmod +x "${EXTRACTED_DIR}/moonx"
    cp "${EXTRACTED_DIR}/moonx" "${BIN_DIR}/moonx"
fi

# Verify
if [ ! -x "${BIN_DIR}/moon" ]; then
    log_error "moon installation failed: ${BIN_DIR}/moon not executable"
    exit 1
fi

log_info "moon installed successfully to ${BIN_DIR}/moon"
"${BIN_DIR}/moon" -version
