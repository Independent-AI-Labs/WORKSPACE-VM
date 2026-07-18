#!/usr/bin/env bash
set -euo pipefail

# Bootstrap OpenVPN client into the platform boot directory.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

_boot_platform="$(uname -s | tr 'A-Z' 'a-z')"
case "$_boot_platform" in darwin) _boot_default=".boot-macos" ;; *) _boot_default=".boot-linux" ;; esac
BOOT_DIR="${BOOT_DIR:-${BOOT_LINUX_DIR:-${PROJECT_ROOT}/${_boot_default}}}"
BIN_DIR="${BOOT_DIR}/bin"
mkdir -p "${BIN_DIR}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

OS="$(uname -s)"

case "${OS}" in
    Darwin)
        log_info "Installing OpenVPN on macOS via Homebrew..."
        if ! command -v brew ; then
            log_error "Homebrew is required. Install from https://brew.sh"
            exit 1
        fi
        brew install openvpn
        OVPN_PREFIX="$(brew --prefix openvpn)"
        OVPN_BIN="${OVPN_PREFIX}/sbin/openvpn"
        if [[ ! -x "$OVPN_BIN" ]]; then
            log_error "openvpn binary not found at $OVPN_BIN after brew install"
            exit 1
        fi
        ln -sf "$OVPN_BIN" "${BIN_DIR}/openvpn"
        ;;
    Linux)
        log_info "Installing OpenVPN via apt..."
        if ! command -v apt-get ; then
            log_error "apt-get not found. Cannot install openvpn on this Linux distribution."
            exit 1
        fi
        sudo apt-get update -qq
        sudo apt-get install -y openvpn
        OVPN_BIN="/usr/sbin/openvpn"
        if [[ ! -x "$OVPN_BIN" ]]; then
            log_error "openvpn binary not found at $OVPN_BIN after apt install"
            exit 1
        fi
        ln -sf "$OVPN_BIN" "${BIN_DIR}/openvpn"
        ;;
    *)
        log_error "Unsupported OS: ${OS}"
        exit 1
        ;;
esac

if ! "${BIN_DIR}/openvpn" --version; then
    log_error "OpenVPN verification failed"
    exit 1
fi

_version_out="$("${BIN_DIR}/openvpn" --version 2>&1)"
_version_line="${_version_out%%$'\n'*}"
log_info "OpenVPN installed: ${_version_line}"
log_info "Symlinked to ${BIN_DIR}/openvpn"

source "${SCRIPT_DIR}/bootstrap_openvpn_service.sh" || exit 1
install_openvpn_service "${PROJECT_ROOT}" "${BIN_DIR}/openvpn"