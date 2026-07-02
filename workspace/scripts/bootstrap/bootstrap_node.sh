#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"
NODE_ENV="${BOOT_LINUX_DIR}/node-env"
PYTHON_ENV_BIN="${BOOT_LINUX_DIR}/python-env/bin"
NODEENV_BIN="${PYTHON_ENV_BIN}/nodeenv"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [ -x "${NODE_ENV}/bin/node" ]; then
    log_info "Node.js already installed at ${NODE_ENV}"
    "${NODE_ENV}/bin/node" --version
    mkdir -p "${BIN_DIR}"
    ln -sf "${NODE_ENV}/bin/node" "${BIN_DIR}/node"
    ln -sf "${NODE_ENV}/bin/npm" "${BIN_DIR}/npm"
    ln -sf "${NODE_ENV}/bin/npx" "${BIN_DIR}/npx"
    exit 0
fi

if [ -x "${BIN_DIR}/uv" ]; then
    UV_CMD="${BIN_DIR}/uv"
else
    log_error "uv not found at ${BIN_DIR}/uv. Run bootstrap_uv.sh first."
    exit 1
fi

if [ ! -x "${NODEENV_BIN}" ]; then
    log_info "nodeenv not found, installing into boot python env..."
    "${UV_CMD}" pip install --python "${PYTHON_ENV_BIN}/python" nodeenv --quiet || {
        log_error "Failed to install nodeenv"
        exit 1
    }
fi

log_info "Creating Node.js environment in ${NODE_ENV}..."

mkdir -p "${BIN_DIR}"

if [ -d "${NODE_ENV}" ]; then
    rm -rf "${NODE_ENV}"
fi

"${NODEENV_BIN}" --node=24.11.1 "${NODE_ENV}" || {
    log_error "Failed to create Node.js environment"
    exit 1
}

ln -sf "${NODE_ENV}/bin/node" "${BIN_DIR}/node"
ln -sf "${NODE_ENV}/bin/npm" "${BIN_DIR}/npm"
ln -sf "${NODE_ENV}/bin/npx" "${BIN_DIR}/npx"

if [ -x "${BIN_DIR}/node" ]; then
    log_info "Node.js installed successfully"
    log_info "  Node env: ${NODE_ENV}"
    log_info "  Symlinks: ${BIN_DIR}/node, ${BIN_DIR}/npm, ${BIN_DIR}/npx"
    "${BIN_DIR}/node" --version
else
    log_error "Node.js installation failed"
    exit 1
fi
