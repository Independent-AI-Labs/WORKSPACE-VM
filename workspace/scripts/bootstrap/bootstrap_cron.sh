#!/usr/bin/env bash
# Bootstrap cron symlink into .boot-linux — requires system cron package via make init
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BOOT_DIR="${BOOT_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"
SYS_CRONTAB="/usr/bin/crontab"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "Linux only."
    exit 1
fi

if [ ! -d "$BOOT_DIR" ]; then
    log_error ".boot-linux directory not found."
    exit 1
fi

if [[ ! -f "$SYS_CRONTAB" ]]; then
    log_error "System crontab not found at $SYS_CRONTAB"
    log_error "Install the cron package: sudo make init  (or: sudo apt-get install cron)"
    exit 1
fi

mkdir -p "${BIN_DIR}"

if [[ -L "${BIN_DIR}/cron" ]]; then
    rm -f "${BIN_DIR}/cron"
fi

log_info "Bootstrapping cron -> $SYS_CRONTAB"
ln -sf "$SYS_CRONTAB" "${BIN_DIR}/cron"

CRON_OUT="$(timeout 5 "${BIN_DIR}/cron" -h 2>&1)"
local _cron_rc=$?
if echo "$CRON_OUT" | grep -q "usage"; then
    log_info "cron bootstrapped successfully"
else
    log_error "cron check failed"
    exit 1
fi
