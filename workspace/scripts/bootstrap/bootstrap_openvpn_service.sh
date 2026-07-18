is-enabled workspace-openvpn.service || enabled_rc=$?#!/usr/bin/env bash
is-enabled workspace-openvpn.service || enabled_rc=$?set -euo pipefail
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?# Install workspace-managed OpenVPN host service (systemd user or LaunchDaemon).
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
is-enabled workspace-openvpn.service || enabled_rc=$?PROJECT_ROOT="${1:-$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
is-enabled workspace-openvpn.service || enabled_rc=$?OPENVPN_BINARY="${2:-}"
is-enabled workspace-openvpn.service || enabled_rc=$?PERSIST_STATE_FILE="${HOME}/.local/state/workspace/openvpn-persist"
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?RED='\033[0;31m'
is-enabled workspace-openvpn.service || enabled_rc=$?GREEN='\033[0;32m'
is-enabled workspace-openvpn.service || enabled_rc=$?YELLOW='\033[1;33m'
is-enabled workspace-openvpn.service || enabled_rc=$?NC='\033[0m'
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
is-enabled workspace-openvpn.service || enabled_rc=$?log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
is-enabled workspace-openvpn.service || enabled_rc=$?log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_workspace_python() {
is-enabled workspace-openvpn.service || enabled_rc=$?    if command -v uv ; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "uv run python"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    if command -v python3 ; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "python3"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    return 1
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_run_workspace_python() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local py
is-enabled workspace-openvpn.service || enabled_rc=$?    if ! py="$(_workspace_python)"; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_error "No Python runtime found (uv or python3)"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 1
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    (
is-enabled workspace-openvpn.service || enabled_rc=$?        cd "${PROJECT_ROOT}" || exit 1
is-enabled workspace-openvpn.service || enabled_rc=$?        export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
is-enabled workspace-openvpn.service || enabled_rc=$?        # shellcheck disable=SC2086
is-enabled workspace-openvpn.service || enabled_rc=$?        ${py} "$@"
is-enabled workspace-openvpn.service || enabled_rc=$?    )
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_render_template_to_file() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local template_name="$1"
is-enabled workspace-openvpn.service || enabled_rc=$?    local output_path="$2"
is-enabled workspace-openvpn.service || enabled_rc=$?    local context_json="$3"
is-enabled workspace-openvpn.service || enabled_rc=$?    _run_workspace_python -c "
is-enabled workspace-openvpn.service || enabled_rc=$?import json
is-enabled workspace-openvpn.service || enabled_rc=$?import sys
is-enabled workspace-openvpn.service || enabled_rc=$?from pathlib import Path
is-enabled workspace-openvpn.service || enabled_rc=$?from workspace.cli.vm_core import _render_template
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?ctx = json.loads(sys.argv[1])
is-enabled workspace-openvpn.service || enabled_rc=$?Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
is-enabled workspace-openvpn.service || enabled_rc=$?Path(sys.argv[2]).write_text(_render_template(sys.argv[3], ctx))
is-enabled workspace-openvpn.service || enabled_rc=$?" "${context_json}" "${output_path}" "${template_name}"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_resolve_service_paths() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local persist_enabled="${1:-false}"
is-enabled workspace-openvpn.service || enabled_rc=$?    _run_workspace_python -c "
is-enabled workspace-openvpn.service || enabled_rc=$?import json
is-enabled workspace-openvpn.service || enabled_rc=$?import sys
is-enabled workspace-openvpn.service || enabled_rc=$?from pathlib import Path
is-enabled workspace-openvpn.service || enabled_rc=$?from workspace.cli.vpn_core import (
is-enabled workspace-openvpn.service || enabled_rc=$?    find_openvpn_binary,
is-enabled workspace-openvpn.service || enabled_rc=$?    resolve_vpn_auth,
is-enabled workspace-openvpn.service || enabled_rc=$?    resolve_vpn_config,
is-enabled workspace-openvpn.service || enabled_rc=$?)
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?root = Path(sys.argv[1]).resolve()
is-enabled workspace-openvpn.service || enabled_rc=$?explicit_binary = sys.argv[2]
is-enabled workspace-openvpn.service || enabled_rc=$?persist_enabled = sys.argv[3] == 'true'
is-enabled workspace-openvpn.service || enabled_rc=$?binary = explicit_binary if explicit_binary else find_openvpn_binary(root)
is-enabled workspace-openvpn.service || enabled_rc=$?config = resolve_vpn_config(root)
is-enabled workspace-openvpn.service || enabled_rc=$?auth = resolve_vpn_auth(root)
is-enabled workspace-openvpn.service || enabled_rc=$?import platform
is-enabled workspace-openvpn.service || enabled_rc=$?if platform.system() == 'Darwin':
is-enabled workspace-openvpn.service || enabled_rc=$?    log_path = Path('/var/log/workspace/openvpn.log')
is-enabled workspace-openvpn.service || enabled_rc=$?else:
is-enabled workspace-openvpn.service || enabled_rc=$?    log_path = Path.home() / '.local' / 'state' / 'workspace' / 'openvpn.log'
is-enabled workspace-openvpn.service || enabled_rc=$?print(json.dumps({
is-enabled workspace-openvpn.service || enabled_rc=$?    'openvpn_binary': binary,
is-enabled workspace-openvpn.service || enabled_rc=$?    'vpn_config': str(config),
is-enabled workspace-openvpn.service || enabled_rc=$?    'vpn_auth': str(auth) if auth else '',
is-enabled workspace-openvpn.service || enabled_rc=$?    'workspace_root': str(root),
is-enabled workspace-openvpn.service || enabled_rc=$?    'log_path': str(log_path),
is-enabled workspace-openvpn.service || enabled_rc=$?    'run_at_load': persist_enabled,
is-enabled workspace-openvpn.service || enabled_rc=$?    'keep_alive': persist_enabled,
is-enabled workspace-openvpn.service || enabled_rc=$?}))
is-enabled workspace-openvpn.service || enabled_rc=$?" "${PROJECT_ROOT}" "${OPENVPN_BINARY}" "${persist_enabled}"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_persist_state_dir() {
is-enabled workspace-openvpn.service || enabled_rc=$?    mkdir -p "$(dirname "${PERSIST_STATE_FILE}")"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_write_persist_state() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local enabled="$1"
is-enabled workspace-openvpn.service || enabled_rc=$?    _persist_state_dir
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ "${enabled}" == "true" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "1" > "${PERSIST_STATE_FILE}"
is-enabled workspace-openvpn.service || enabled_rc=$?    else
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "0" > "${PERSIST_STATE_FILE}"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_read_persist_state() {
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ -f "${PERSIST_STATE_FILE}" ]] && grep -q '^1$' "${PERSIST_STATE_FILE}"; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "true"
is-enabled workspace-openvpn.service || enabled_rc=$?    else
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "false"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_install_linux_unit() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local context_json="$1"
is-enabled workspace-openvpn.service || enabled_rc=$?    local unit_dir="${HOME}/.config/systemd/user"
is-enabled workspace-openvpn.service || enabled_rc=$?    local unit_path="${unit_dir}/workspace-openvpn.service"
is-enabled workspace-openvpn.service || enabled_rc=$?    mkdir -p "${unit_dir}"
is-enabled workspace-openvpn.service || enabled_rc=$?    _render_template_to_file \
is-enabled workspace-openvpn.service || enabled_rc=$?        "systemd-openvpn-client.service.j2" \
is-enabled workspace-openvpn.service || enabled_rc=$?        "${unit_path}" \
is-enabled workspace-openvpn.service || enabled_rc=$?        "${context_json}"
is-enabled workspace-openvpn.service || enabled_rc=$?    systemctl --user daemon-reload
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_install_darwin_daemon() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local context_json="$1"
is-enabled workspace-openvpn.service || enabled_rc=$?    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
is-enabled workspace-openvpn.service || enabled_rc=$?    local rendered_plist
is-enabled workspace-openvpn.service || enabled_rc=$?    rendered_plist="$(mktemp)"
is-enabled workspace-openvpn.service || enabled_rc=$?    _render_template_to_file \
is-enabled workspace-openvpn.service || enabled_rc=$?        "launchd-openvpn-client.plist.j2" \
is-enabled workspace-openvpn.service || enabled_rc=$?        "${rendered_plist}" \
is-enabled workspace-openvpn.service || enabled_rc=$?        "${context_json}"
is-enabled workspace-openvpn.service || enabled_rc=$?    _gui_bootout_rc=0
is-enabled workspace-openvpn.service || enabled_rc=$?    launchctl bootout "gui/$(id -u)/workspace.openvpn.client" || _gui_bootout_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [ "${_gui_bootout_rc}" -ne 0 ]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_info "gui LaunchAgent not loaded (bootout exit ${_gui_bootout_rc})"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    rm -f "${HOME}/Library/LaunchAgents/workspace.openvpn.client.plist"
is-enabled workspace-openvpn.service || enabled_rc=$?    sudo mkdir -p /var/log/workspace
is-enabled workspace-openvpn.service || enabled_rc=$?    sudo cp "${rendered_plist}" "${plist_path}"
is-enabled workspace-openvpn.service || enabled_rc=$?    sudo chmod 644 "${plist_path}"
is-enabled workspace-openvpn.service || enabled_rc=$?    rm -f "${rendered_plist}"
is-enabled workspace-openvpn.service || enabled_rc=$?    _system_bootout_rc=0
is-enabled workspace-openvpn.service || enabled_rc=$?    sudo launchctl bootout system/workspace.openvpn.client || _system_bootout_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [ "${_system_bootout_rc}" -ne 0 ]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_info "system LaunchDaemon not loaded (bootout exit ${_system_bootout_rc})"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    if ! sudo launchctl bootstrap system "${plist_path}"; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_error "launchctl bootstrap failed for ${plist_path}"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 1
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_linux_persist_on() {
is-enabled workspace-openvpn.service || enabled_rc=$?    systemctl --user enable workspace-openvpn.service
is-enabled workspace-openvpn.service || enabled_rc=$?    if command -v loginctl ; then
is-enabled workspace-openvpn.service || enabled_rc=$?        loginctl enable-linger "$(id -un)"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_linux_persist_off() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local disable_rc=0
is-enabled workspace-openvpn.service || enabled_rc=$?    systemctl --user disable workspace-openvpn.service || disable_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [ "${disable_rc}" -ne 0 ]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_info "workspace-openvpn.service already disabled (exit ${disable_rc})"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_linux_persist_status() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local enabled_rc=0
    systemctl --user is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [ "${enabled_rc}" -eq 0 ]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "enabled"
is-enabled workspace-openvpn.service || enabled_rc=$?    else
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "disabled"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_darwin_plist_binary() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ ! -f "${plist_path}" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo ""
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    local binary=""
is-enabled workspace-openvpn.service || enabled_rc=$?    local extract_rc=0
is-enabled workspace-openvpn.service || enabled_rc=$?    binary="$(plutil -extract ProgramArguments.0 raw "${plist_path}" 2>&1)" || extract_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [ "${extract_rc}" -ne 0 ]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo ""
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    echo "${binary}"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_darwin_persist_status() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ ! -f "${plist_path}" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "missing"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    local run_at_load=""
is-enabled workspace-openvpn.service || enabled_rc=$?    local extract_rc=0
is-enabled workspace-openvpn.service || enabled_rc=$?    run_at_load="$(plutil -extract RunAtLoad raw "${plist_path}" 2>&1)" || extract_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [ "${extract_rc}" -ne 0 ]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "disabled"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    if echo "${run_at_load}" | grep -q 'true'; then
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "enabled"
is-enabled workspace-openvpn.service || enabled_rc=$?    else
is-enabled workspace-openvpn.service || enabled_rc=$?        echo "disabled"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?_darwin_plist_needs_reinstall() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local expected_binary="$1"
is-enabled workspace-openvpn.service || enabled_rc=$?    local installed_binary
is-enabled workspace-openvpn.service || enabled_rc=$?    installed_binary="$(_darwin_plist_binary)"
is-enabled workspace-openvpn.service || enabled_rc=$?    [[ -n "${expected_binary}" && "${installed_binary}" != "${expected_binary}" ]]
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?install_openvpn_service() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local project_root="${1:-${PROJECT_ROOT}}"
is-enabled workspace-openvpn.service || enabled_rc=$?    local openvpn_binary="${2:-}"
is-enabled workspace-openvpn.service || enabled_rc=$?    PROJECT_ROOT="${project_root}"
is-enabled workspace-openvpn.service || enabled_rc=$?    OPENVPN_BINARY="${openvpn_binary}"
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local canonical_config="${PROJECT_ROOT}/workspace/config/vpn/client.ovpn"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ ! -f "${canonical_config}" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_warn "Skipping OpenVPN service install: canonical config missing at ${canonical_config}"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    configure_openvpn_persist "false"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?configure_openvpn_persist() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local persist_enabled="${1:-false}"
is-enabled workspace-openvpn.service || enabled_rc=$?    local project_root="${2:-${PROJECT_ROOT}}"
is-enabled workspace-openvpn.service || enabled_rc=$?    local openvpn_binary="${3:-${OPENVPN_BINARY}}"
is-enabled workspace-openvpn.service || enabled_rc=$?    PROJECT_ROOT="${project_root}"
is-enabled workspace-openvpn.service || enabled_rc=$?    OPENVPN_BINARY="${openvpn_binary}"
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local canonical_config="${PROJECT_ROOT}/workspace/config/vpn/client.ovpn"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ ! -f "${canonical_config}" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_error "Cannot configure persistence: canonical config missing at ${canonical_config}"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 1
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local desired_status="disabled"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ "${persist_enabled}" == "true" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        desired_status="enabled"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    local context_json
is-enabled workspace-openvpn.service || enabled_rc=$?    if ! context_json="$(_resolve_service_paths "${persist_enabled}")"; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_error "Failed to resolve OpenVPN service paths"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 1
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local current_status
is-enabled workspace-openvpn.service || enabled_rc=$?    current_status="$(openvpn_persist_status)"
is-enabled workspace-openvpn.service || enabled_rc=$?    local needs_reinstall="false"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ "$(uname -s)" == "Darwin" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        local expected_binary
is-enabled workspace-openvpn.service || enabled_rc=$?        expected_binary="$(echo "${context_json}" | _run_workspace_python -c "import json,sys; print(json.load(sys.stdin)['openvpn_binary'])")"
is-enabled workspace-openvpn.service || enabled_rc=$?        if _darwin_plist_needs_reinstall "${expected_binary}"; then
is-enabled workspace-openvpn.service || enabled_rc=$?            needs_reinstall="true"
is-enabled workspace-openvpn.service || enabled_rc=$?            log_info "LaunchDaemon binary path mismatch; reinstalling plist"
is-enabled workspace-openvpn.service || enabled_rc=$?        fi
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ "${current_status}" == "${desired_status}" && "${needs_reinstall}" == "false" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_info "Persist already ${desired_status}; skipping service reinstall"
is-enabled workspace-openvpn.service || enabled_rc=$?        _write_persist_state "${persist_enabled}"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local os
is-enabled workspace-openvpn.service || enabled_rc=$?    os="$(uname -s)"
is-enabled workspace-openvpn.service || enabled_rc=$?    case "${os}" in
is-enabled workspace-openvpn.service || enabled_rc=$?        Linux)
is-enabled workspace-openvpn.service || enabled_rc=$?            _install_linux_unit "${context_json}"
is-enabled workspace-openvpn.service || enabled_rc=$?            if [[ "${persist_enabled}" == "true" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?                _linux_persist_on
is-enabled workspace-openvpn.service || enabled_rc=$?                log_info "Enabled workspace-openvpn.service at login/boot (linger on)"
is-enabled workspace-openvpn.service || enabled_rc=$?            else
is-enabled workspace-openvpn.service || enabled_rc=$?                _linux_persist_off
is-enabled workspace-openvpn.service || enabled_rc=$?                log_info "Disabled workspace-openvpn.service auto-start at login/boot"
is-enabled workspace-openvpn.service || enabled_rc=$?            fi
is-enabled workspace-openvpn.service || enabled_rc=$?            ;;
is-enabled workspace-openvpn.service || enabled_rc=$?        Darwin)
is-enabled workspace-openvpn.service || enabled_rc=$?            _install_darwin_daemon "${context_json}"
is-enabled workspace-openvpn.service || enabled_rc=$?            log_info "Installed LaunchDaemon with RunAtLoad=${persist_enabled}"
is-enabled workspace-openvpn.service || enabled_rc=$?            ;;
is-enabled workspace-openvpn.service || enabled_rc=$?        *)
is-enabled workspace-openvpn.service || enabled_rc=$?            log_error "Unsupported OS for OpenVPN service install: ${os}"
is-enabled workspace-openvpn.service || enabled_rc=$?            return 1
is-enabled workspace-openvpn.service || enabled_rc=$?            ;;
is-enabled workspace-openvpn.service || enabled_rc=$?    esac
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    _write_persist_state "${persist_enabled}"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?openvpn_persist_status() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local os
is-enabled workspace-openvpn.service || enabled_rc=$?    os="$(uname -s)"
is-enabled workspace-openvpn.service || enabled_rc=$?    case "${os}" in
is-enabled workspace-openvpn.service || enabled_rc=$?        Linux) _linux_persist_status ;;
is-enabled workspace-openvpn.service || enabled_rc=$?        Darwin) _darwin_persist_status ;;
is-enabled workspace-openvpn.service || enabled_rc=$?        *) echo "unsupported" ;;
is-enabled workspace-openvpn.service || enabled_rc=$?    esac
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?ensure_openvpn_daemon_installed() {
is-enabled workspace-openvpn.service || enabled_rc=$?    local project_root="${1:-${PROJECT_ROOT}}"
is-enabled workspace-openvpn.service || enabled_rc=$?    local openvpn_binary="${2:-${OPENVPN_BINARY}}"
is-enabled workspace-openvpn.service || enabled_rc=$?    PROJECT_ROOT="${project_root}"
is-enabled workspace-openvpn.service || enabled_rc=$?    OPENVPN_BINARY="${openvpn_binary}"
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ "$(uname -s)" != "Darwin" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local canonical_config="${PROJECT_ROOT}/workspace/config/vpn/client.ovpn"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ ! -f "${canonical_config}" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_error "Cannot ensure LaunchDaemon: canonical config missing at ${canonical_config}"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 1
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local expected_binary
is-enabled workspace-openvpn.service || enabled_rc=$?    if ! expected_binary="$(_resolve_service_paths "false" | _run_workspace_python -c "import json,sys; print(json.load(sys.stdin)['openvpn_binary'])")"; then
is-enabled workspace-openvpn.service || enabled_rc=$?        log_error "Failed to resolve OpenVPN binary for LaunchDaemon"
is-enabled workspace-openvpn.service || enabled_rc=$?        return 1
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local plist_path="/Library/LaunchDaemons/workspace.openvpn.client.plist"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ -f "${plist_path}" ]] && ! _darwin_plist_needs_reinstall "${expected_binary}"; then
is-enabled workspace-openvpn.service || enabled_rc=$?        return 0
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?    local persist_enabled="false"
is-enabled workspace-openvpn.service || enabled_rc=$?    if [[ "$(openvpn_persist_status)" == "enabled" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?        persist_enabled="true"
is-enabled workspace-openvpn.service || enabled_rc=$?    fi
is-enabled workspace-openvpn.service || enabled_rc=$?    log_info "Refreshing LaunchDaemon plist (binary: ${expected_binary})"
is-enabled workspace-openvpn.service || enabled_rc=$?    configure_openvpn_persist "${persist_enabled}" "${PROJECT_ROOT}" "${expected_binary}"
is-enabled workspace-openvpn.service || enabled_rc=$?}
is-enabled workspace-openvpn.service || enabled_rc=$?
is-enabled workspace-openvpn.service || enabled_rc=$?if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
is-enabled workspace-openvpn.service || enabled_rc=$?    install_openvpn_service "${PROJECT_ROOT}" "${OPENVPN_BINARY}"
is-enabled workspace-openvpn.service || enabled_rc=$?fi