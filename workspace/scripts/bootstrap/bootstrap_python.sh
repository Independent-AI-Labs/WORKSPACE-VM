#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Python venv into .boot-linux using uv
# Creates .boot-linux/bin/python for use by other bootstrap scripts

_SELF="${BASH_SOURCE[0]}"
if [ -n "${SHG_SCRIPT_PATH:-}" ]; then _SELF="$SHG_SCRIPT_PATH"; fi
SCRIPT_DIR="$(cd "$(dirname "$_SELF")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

_boot_platform="$(uname -s | tr 'A-Z' 'a-z')"
case "$_boot_platform" in darwin) _boot_default=".boot-macos" ;; *) _boot_default=".boot-linux" ;; esac
BOOT_LINUX_DIR="${BOOT_LINUX_DIR:-${BOOT_DIR:-${PROJECT_ROOT}/${_boot_default}}}"
BIN_DIR="${BOOT_LINUX_DIR}/bin"
PYTHON_ENV="${BOOT_LINUX_DIR}/python-env"

_ci_boot_name=".boot-linux"
if [[ "$_boot_platform" == "darwin" ]]; then
    _ci_boot_name=".boot-macos"
fi
CI_UV="${PROJECT_ROOT}/projects/CI/${_ci_boot_name}/bin/uv"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Resolve required Python version from pyproject.toml requires-python.
# Extracts the major.minor version (e.g. "3.13") from patterns like:
#   ==3.13.*  >=3.13  ==3.11.*  >=3.11,<3.14
_PYPROJECT="${PROJECT_ROOT}/pyproject.toml"
if [[ ! -f "$_PYPROJECT" ]]; then
    log_error "pyproject.toml not found at ${_PYPROJECT}"
    exit 1
fi
REQUIRED_PYTHON="$(grep -m1 'requires-python' "$_PYPROJECT")"
if [[ -z "$REQUIRED_PYTHON" ]]; then
    log_error "requires-python not found in ${_PYPROJECT}"
    exit 1
fi
# Extract the quoted value from the grep line
REQUIRED_PYTHON="${REQUIRED_PYTHON#*\"}"
REQUIRED_PYTHON="${REQUIRED_PYTHON%\"*}"
if [[ -z "$REQUIRED_PYTHON" ]]; then
    log_error "requires-python value is empty in ${_PYPROJECT}"
    exit 1
fi
# Extract major.minor from the constraint (first X.Y pair found)
# Use bash regex instead of piping to grep to avoid pipefail masking
if [[ "$REQUIRED_PYTHON" =~ ([0-9]+\.[0-9]+) ]]; then
    PY_VERSION="${BASH_REMATCH[1]}"
else
    log_error "Cannot parse Python version from requires-python='${REQUIRED_PYTHON}'"
    exit 1
fi
log_info "Required Python: ${PY_VERSION} (from pyproject.toml requires-python=\"${REQUIRED_PYTHON}\")"

# Check symlink target, not just bin/python
if [ -x "${PYTHON_ENV}/bin/python" ]; then
    _current_ver="$("${PYTHON_ENV}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ "$_current_ver" == "$PY_VERSION" ]]; then
        log_info "Python ${PY_VERSION} already installed at ${PYTHON_ENV}"
        "${PYTHON_ENV}/bin/python" --version
        # Symlink recreation belongs on the fresh-install path only.
        # BIN_DIR (.boot-linux/bin) is root:root 0755 on provisioned VMs,
        # so mkdir + ln -sf here would hit Permission denied for uid 1000.
        # If a symlink is genuinely broken, re-running `make core` from
        # the operator (or fixing the link as root) is the correct path.
        exit 0
    fi
    log_info "Python ${_current_ver} found at ${PYTHON_ENV}, upgrading to ${PY_VERSION}..."
    rm -rf "${PYTHON_ENV}"
fi

# Find uv: CI boot dir first (make core delegates uv to projects/CI), then workspace boot bin.
if [ -x "${CI_UV}" ]; then
    UV_CMD="${CI_UV}"
elif [ -x "${BIN_DIR}/uv" ]; then
    UV_CMD="${BIN_DIR}/uv"
else
    log_error "uv not found at ${CI_UV} or ${BIN_DIR}/uv. Run 'make core' first."
    exit 1
fi

log_info "Creating Python venv in ${PYTHON_ENV} using uv..."

# Containment: uv-managed interpreters live inside the boot dir, never in
# $HOME/.local/share/uv/python (no unsanctioned HOME/system resources)
export UV_PYTHON_INSTALL_DIR="${BOOT_LINUX_DIR}/python"

# Create directories
mkdir -p "${BIN_DIR}"

# Create venv in subdirectory (not at .boot-linux root)
# Python version resolved from pyproject.toml requires-python above.
"$UV_CMD" venv "${PYTHON_ENV}" --seed --python "$PY_VERSION"

# Symlink to bin/ so other scripts can find the binary
ln -sf "${PYTHON_ENV}/bin/python" "${BIN_DIR}/python"
ln -sf "${PYTHON_ENV}/bin/pip" "${BIN_DIR}/pip"

# Verify
if [ -x "${BIN_DIR}/python" ]; then
    log_info "Python installed successfully"
    log_info "  Venv: ${PYTHON_ENV}"
    log_info "  Symlink: ${BIN_DIR}/python"
    "${BIN_DIR}/python" --version
else
    log_error "Python installation failed"
    exit 1
fi
