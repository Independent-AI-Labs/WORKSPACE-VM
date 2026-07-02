#!/usr/bin/env bash
set -euo pipefail

# Cloc Bootstrap Script for WORKSPACE-VM
# Downloads and installs cloc (Count Lines of Code) into the .boot-linux environment.
# cloc is a single-file Perl script - just drop it in bin/ and chmod +x.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

VENV_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"

CLOC_VERSION="2.02"
CLOC_URL="https://github.com/AlDanial/cloc/releases/download/v${CLOC_VERSION}/cloc-${CLOC_VERSION}.pl"
CLOC_BIN="${VENV_DIR}/bin/cloc"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if ! command -v perl >/dev/null 2>&1; then
    log_error "perl is required by cloc but was not found in PATH"
    exit 1
fi

mkdir -p "${VENV_DIR}/bin"

log_info "Downloading cloc ${CLOC_VERSION} from ${CLOC_URL}"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "${CLOC_BIN}" "${CLOC_URL}"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "${CLOC_BIN}" "${CLOC_URL}"
else
    log_error "Neither curl nor wget found"
    exit 1
fi

chmod +x "${CLOC_BIN}"

log_info "Verifying cloc installation"
if "${CLOC_BIN}" -version >/dev/null 2>&1; then
    log_info "cloc installed: $(${CLOC_BIN} -version)"
    log_info "Binary: ${CLOC_BIN}"
else
    log_error "cloc verification failed"
    exit 1
fi
