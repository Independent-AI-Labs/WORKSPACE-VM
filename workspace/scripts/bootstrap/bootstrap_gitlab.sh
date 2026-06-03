#!/usr/bin/env bash
# GitLab CLI Bootstrap Script for AMI-AGENTS
# Downloads and installs glab in the .boot-linux environment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"
GLAB_DIR="${BOOT_DIR}/glab"
mkdir -p "${BIN_DIR}" "${GLAB_DIR}"

GLAB_VERSION="1.54.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*" >&2; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

OS="$(uname -s)"
ARCH="$(uname -m)"

case "${OS}" in
    Linux)  OS_TYPE="linux" ;;
    Darwin) OS_TYPE="macOS" ;;
    *)
        log_error "Unsupported OS: ${OS}"
        exit 1
        ;;
esac

case "${ARCH}" in
    x86_64)        ARCH_TYPE="amd64" ;;
    aarch64|arm64) ARCH_TYPE="arm64" ;;
    *)
        log_error "Unsupported architecture: ${ARCH}"
        exit 1
        ;;
esac

ARCHIVE_NAME="glab_${GLAB_VERSION}_${OS_TYPE}_${ARCH_TYPE}.tar.gz"
DOWNLOAD_URL="https://gitlab.com/gitlab-org/cli/-/releases/v${GLAB_VERSION}/downloads/${ARCHIVE_NAME}"

log_info "Bootstrapping glab ${GLAB_VERSION} (${OS_TYPE}/${ARCH_TYPE}) into ${GLAB_DIR}"
log_info "Downloading from ${DOWNLOAD_URL}..."

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if command -v curl &> /dev/null; then
    curl -fSL -o "${TEMP_DIR}/${ARCHIVE_NAME}" "${DOWNLOAD_URL}"
elif command -v wget &> /dev/null; then
    wget -O "${TEMP_DIR}/${ARCHIVE_NAME}" "${DOWNLOAD_URL}"
else
    log_error "Neither curl nor wget found."
    exit 1
fi

log_info "Extracting ${ARCHIVE_NAME}..."
tar -xzf "${TEMP_DIR}/${ARCHIVE_NAME}" -C "${TEMP_DIR}"

EXTRACTED_BIN="${TEMP_DIR}/bin/glab"
if [[ ! -f "$EXTRACTED_BIN" ]]; then
    log_error "glab binary not found in archive"
    ls -laR "${TEMP_DIR}/" >&2 || true  # silent-ok: diagnostic dump, binary-not-found already errors above
    exit 1
fi

rm -rf "${GLAB_DIR:?}"/*
cp -r "${TEMP_DIR}/bin" "${GLAB_DIR}/"
chmod +x "${GLAB_DIR}/bin/glab"

ln -sf "../glab/bin/glab" "${BIN_DIR}/glab"

if "${BIN_DIR}/glab" --version > /dev/null 2>&1; then
    GLAB_VER="$("${BIN_DIR}/glab" --version 2>&1 || true)"  # silent-ok: binary verified above, version extraction best-effort
    GLAB_VER="$(echo "$GLAB_VER" | head -n 1)"  # silent-ok: log formatting only, binary already verified
    log_info "glab installed successfully: $GLAB_VER"
    log_info "Location: ${BIN_DIR}/glab -> ${GLAB_DIR}/bin/glab"
else
    log_error "glab installation failed or binary incompatible"
    rm -f "${BIN_DIR}/glab"
    exit 1
fi
