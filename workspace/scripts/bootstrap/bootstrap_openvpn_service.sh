#!/usr/bin/env bash
set -euo pipefail

# Install workspace-managed OpenVPN host service (systemd user or LaunchDaemon).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${1:-$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
OPENVPN_BINARY="${2:-}"
PERSIST_STATE_FILE="${HOME}/.local/state/workspace/openvpn-persist"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

_workspace_python() {
    if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
        echo "${PROJECT_ROOT}/.venv/bin/python"
        return 0
    fi
    if command -v uv &>/dev/null; then
        echo "uv run python"
        return 0
    fi
    if command -v python3 &>/dev/null; then
        echo "python3"
        return 0
    fi
    return 1
}

_run_workspace_python() {
    local py
    if ! py="$(_workspace_python)"; then
        log_error "No Python runtime found (.venv/bin/python, uv, or python3)"
        return 1
    fi
    (
        cd "${PROJECT_ROOT}" || exit 1
        export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
        # shellcheck disable=SC2086
        ${py} "$@"
    )
}

_render_template_to_file() {
    local template_name="$1"
    local output_path="$2"
    local context_json="$3"
    _run_workspace_python -c "
import json
import sys
from pathlib import Path
from workspace.cli.vm_core import _render_template

ctx = json.loads(sys.argv[1])
Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
Path(sys.argv[2]).write_text(_render_template(sys.argv[3], ctx))
" "${context_json}" "${output_path}" "${template_name}"
}

_resolve_service_paths() {
    local persist_enabled="${1:-false}"
    _run_workspace_python -c "
import json
import sys
from pathlib import Path
from workspace.cli.vpn_core import (
    find_openvpn_binary,
    resolve_vpn_auth,
    resolve_vpn_config,
)

root = Path(sys.argv[1]).resolve()
explicit_binary = sys.argv[2]
persist_enabled = sys.argv[3] == 'true'
binary = explicit_binary if explicit_binary else find_openvpn_binary(root)
config = resolve_vpn_config(root)
auth = resolve_vpn_auth(root)
import platform
if platform.system() == 'Darwin':
    log_path = Path('/var/log/workspace/openvpn.log')
else:
    log_path = Path.home() / '.local' / 'state' / 'workspace' / 'openvpn.log'
print(json.dumps({
    'openvpn_binary': binary,
    'vpn_config': str(config),
    'vpn_auth': str(auth) if auth else '',
    'workspace_root': str(root),
    'log_path': str(log_path),
    'run_at_load': persist_enabled,
    'keep_alive': persist_enabled,
}))
" "${PROJECT_ROOT}" "${OPENVPN_BINARY}" "${persist_enabled}"
}

_persist_state_dir() {
    mkdir -p "$(dirname "${PERSIST_STATE_FILE}")"
}

_write_persist_state() {
    local enabled="$1"
    _persist_state_dir
    if [[ "${enabled}" == "true" ]]; then
        echo "1" > "${PERSIST_STATE_FILE}"
    else
        echo "0" > "${PERSIST_STATE_FILE}"
    fi
}

_read_persist_state() {
    if [[ -f "${PERSIST_STATE_FILE}" ]] && grep -q '^1$' "${PERSIST_STATE_FILE}"; then
        echo "true"
    else
        echo "false"
    fi
}

_install_linux_unit() {
    local context_json="$1"
    local unit_dir="${HOME}/.config/systemd/user"
    local unit_path="${unit_dir}/workspace-openvpn.service"
    mkdir -p "${unit_dir}"
    _render_template_to_file \
        "systemd-openvpn-client.service.j2" \
        "${unit_path}" \
        "${context_json}"
    systemctl --user daemon-reload
}

_install_darwin_daemon() {
    local context_json="$1"
    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
    local rendered_plist
    rendered_plist="$(mktemp)"
    _render_template_to_file \
        "launchd-openvpn-client.plist.j2" \
        "${rendered_plist}" \
        "${context_json}"
    _gui_bootout_rc=0
    launchctl bootout "gui/$(id -u)/workspace.openvpn.client" || _gui_bootout_rc=$?
    if [ "${_gui_bootout_rc}" -ne 0 ]; then
        log_info "gui LaunchAgent not loaded (bootout exit ${_gui_bootout_rc})"
    fi
    rm -f "${HOME}/Library/LaunchAgents/workspace.openvpn.client.plist"
    sudo mkdir -p /var/log/workspace
    sudo cp "${rendered_plist}" "${plist_path}"
    sudo chmod 644 "${plist_path}"
    rm -f "${rendered_plist}"
    _system_bootout_rc=0
    sudo launchctl bootout system/workspace.openvpn.client || _system_bootout_rc=$?
    if [ "${_system_bootout_rc}" -ne 0 ]; then
        log_info "system LaunchDaemon not loaded (bootout exit ${_system_bootout_rc})"
    fi
    if ! sudo launchctl bootstrap system "${plist_path}"; then
        log_error "launchctl bootstrap failed for ${plist_path}"
        return 1
    fi
}

_linux_persist_on() {
    systemctl --user enable workspace-openvpn.service
    if command -v loginctl &>/dev/null; then
        loginctl enable-linger "$(id -un)"
    fi
}

_linux_persist_off() {
    local disable_rc=0
    systemctl --user disable workspace-openvpn.service || disable_rc=$?
    if [ "${disable_rc}" -ne 0 ]; then
        log_info "workspace-openvpn.service already disabled (exit ${disable_rc})"
    fi
}

_linux_persist_status() {
    local enabled_rc=0
    systemctl --user is-enabled workspace-openvpn.service >/dev/null 2>&1 || enabled_rc=$?
    if [ "${enabled_rc}" -eq 0 ]; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

_darwin_plist_binary() {
    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
    if [[ ! -f "${plist_path}" ]]; then
        echo ""
        return 0
    fi
    local binary=""
    local extract_rc=0
    binary="$(plutil -extract ProgramArguments.0 raw "${plist_path}" 2>&1)" || extract_rc=$?
    if [ "${extract_rc}" -ne 0 ]; then
        echo ""
        return 0
    fi
    echo "${binary}"
}

_darwin_persist_status() {
    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
    if [[ ! -f "${plist_path}" ]]; then
        echo "missing"
        return 0
    fi
    local run_at_load=""
    local extract_rc=0
    run_at_load="$(plutil -extract RunAtLoad raw "${plist_path}" 2>&1)" || extract_rc=$?
    if [ "${extract_rc}" -ne 0 ]; then
        echo "disabled"
        return 0
    fi
    if echo "${run_at_load}" | grep -q 'true'; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

_darwin_plist_needs_reinstall() {
    local expected_binary="$1"
    local installed_binary
    installed_binary="$(_darwin_plist_binary)"
    [[ -n "${expected_binary}" && "${installed_binary}" != "${expected_binary}" ]]
}

install_openvpn_service() {
    local project_root="${1:-${PROJECT_ROOT}}"
    local openvpn_binary="${2:-}"
    PROJECT_ROOT="${project_root}"
    OPENVPN_BINARY="${openvpn_binary}"

    local canonical_config="${PROJECT_ROOT}/workspace/config/vpn/client.ovpn"
    if [[ ! -f "${canonical_config}" ]]; then
        log_warn "Skipping OpenVPN service install: canonical config missing at ${canonical_config}"
        return 0
    fi

    configure_openvpn_persist "false"
}

configure_openvpn_persist() {
    local persist_enabled="${1:-false}"
    local project_root="${2:-${PROJECT_ROOT}}"
    local openvpn_binary="${3:-${OPENVPN_BINARY}}"
    PROJECT_ROOT="${project_root}"
    OPENVPN_BINARY="${openvpn_binary}"

    local canonical_config="${PROJECT_ROOT}/workspace/config/vpn/client.ovpn"
    if [[ ! -f "${canonical_config}" ]]; then
        log_error "Cannot configure persistence: canonical config missing at ${canonical_config}"
        return 1
    fi

    local desired_status="disabled"
    if [[ "${persist_enabled}" == "true" ]]; then
        desired_status="enabled"
    fi
    local context_json
    if ! context_json="$(_resolve_service_paths "${persist_enabled}")"; then
        log_error "Failed to resolve OpenVPN service paths"
        return 1
    fi

    local current_status
    current_status="$(openvpn_persist_status)"
    local needs_reinstall="false"
    if [[ "$(uname -s)" == "Darwin" ]]; then
        local expected_binary
        expected_binary="$(echo "${context_json}" | _run_workspace_python -c "import json,sys; print(json.load(sys.stdin)['openvpn_binary'])")"
        if _darwin_plist_needs_reinstall "${expected_binary}"; then
            needs_reinstall="true"
            log_info "LaunchDaemon binary path mismatch; reinstalling plist"
        fi
    fi
    if [[ "${current_status}" == "${desired_status}" && "${needs_reinstall}" == "false" ]]; then
        log_info "Persist already ${desired_status}; skipping service reinstall"
        _write_persist_state "${persist_enabled}"
        return 0
    fi

    local os
    os="$(uname -s)"
    case "${os}" in
        Linux)
            _install_linux_unit "${context_json}"
            if [[ "${persist_enabled}" == "true" ]]; then
                _linux_persist_on
                log_info "Enabled workspace-openvpn.service at login/boot (linger on)"
            else
                _linux_persist_off
                log_info "Disabled workspace-openvpn.service auto-start at login/boot"
            fi
            ;;
        Darwin)
            _install_darwin_daemon "${context_json}"
            log_info "Installed LaunchDaemon with RunAtLoad=${persist_enabled}"
            ;;
        *)
            log_error "Unsupported OS for OpenVPN service install: ${os}"
            return 1
            ;;
    esac

    _write_persist_state "${persist_enabled}"
}

openvpn_persist_status() {
    local os
    os="$(uname -s)"
    case "${os}" in
        Linux) _linux_persist_status ;;
        Darwin) _darwin_persist_status ;;
        *) echo "unsupported" ;;
    esac
}

ensure_openvpn_daemon_installed() {
    local project_root="${1:-${PROJECT_ROOT}}"
    local openvpn_binary="${2:-${OPENVPN_BINARY}}"
    PROJECT_ROOT="${project_root}"
    OPENVPN_BINARY="${openvpn_binary}"

    if [[ "$(uname -s)" != "Darwin" ]]; then
        return 0
    fi

    local canonical_config="${PROJECT_ROOT}/workspace/config/vpn/client.ovpn"
    if [[ ! -f "${canonical_config}" ]]; then
        log_error "Cannot ensure LaunchDaemon: canonical config missing at ${canonical_config}"
        return 1
    fi

    local expected_binary
    if ! expected_binary="$(_resolve_service_paths "false" | _run_workspace_python -c "import json,sys; print(json.load(sys.stdin)['openvpn_binary'])")"; then
        log_error "Failed to resolve OpenVPN binary for LaunchDaemon"
        return 1
    fi

    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
    if [[ -f "${plist_path}" ]] && ! _darwin_plist_needs_reinstall "${expected_binary}"; then
        return 0
    fi

    local persist_enabled="false"
    if [[ "$(openvpn_persist_status)" == "enabled" ]]; then
        persist_enabled="true"
    fi
    log_info "Refreshing LaunchDaemon plist (binary: ${expected_binary})"
    configure_openvpn_persist "${persist_enabled}" "${PROJECT_ROOT}" "${expected_binary}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    install_openvpn_service "${PROJECT_ROOT}" "${OPENVPN_BINARY}"
fi