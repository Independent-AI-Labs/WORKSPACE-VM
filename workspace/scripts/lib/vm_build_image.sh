#!/usr/bin/env bash
# Container image build for the workspace VM.
# Sourced by launch-mac.sh. Requires vm_credentials.sh to be loaded.

set -euo pipefail

build_image() {
    log_section "Building Container Image"

    if podman image exists "$FULL_IMAGE" && [[ "$FORCE_REBUILD" != "true" ]]; then
        log_ok "Image '$FULL_IMAGE' already exists (use --force-rebuild to rebuild)"
        return 0
    fi

    local vm_dir="${VMS_DIR}/${CONTAINER_NAME}"
    mkdir -p "$vm_dir"
    mkdir -p "${vm_dir}/certs"

    generate_password
    generate_ssl_certs

    log_info "Generating build context..."

    local install_defaults="${vm_dir}/install-defaults.yaml"
    if [[ -f "$VM_CONFIG_PATH" ]]; then
        "${PROJECT_ROOT}/.venv-mac/bin/python" -c "
import yaml
import sys

with open('$VM_CONFIG_PATH') as f:
    cfg = yaml.safe_load(f)

components = cfg.get('components', ['uv', 'python', 'node', 'opencode'])
with open('$install_defaults', 'w') as f:
    yaml.dump({'components': components}, f)
"
    else
        log_warn "Config not found at $VM_CONFIG_PATH, using defaults"
        cat > "$install_defaults" <<'YAML'
components:
  - uv
  - python
  - node
  - opencode
  - podman
YAML
    fi

    log_info "Generating service files..."

    local templates_dir="${PROJECT_ROOT}/workspace/scripts/templates"
    local python_bin="${PROJECT_ROOT}/.venv-mac/bin/python"
    local renderer="${PROJECT_ROOT}/workspace/scripts/lib/render_build_context.sh"

    if [[ ! -x "$python_bin" ]]; then
        log_error "Python venv not found at $python_bin. Run install-mac.sh first."
        exit 1
    fi

    if [[ ! -x "$renderer" ]]; then
        log_error "Build context renderer not found at $renderer"
        exit 1
    fi

    "$renderer" "$PROJECT_ROOT" "$vm_dir" "$PASSWORD_FILE" "$templates_dir" "$python_bin"

    log_info "Building image '$FULL_IMAGE'..."
    log_info "This may take several minutes on first build..."

    local dockerfile="${vm_dir}/Dockerfile"
    local temp_ssh_key=""
    if [[ -f "$HOME/.ssh/id_rsa" ]]; then
        log_info "SSH key forwarding via temporary copy"
        temp_ssh_key="${vm_dir}/temp_ssh_key"
        cp "$HOME/.ssh/id_rsa" "$temp_ssh_key"
        chmod 600 "$temp_ssh_key"
    fi

    trap "rm -f '$temp_ssh_key'" EXIT

    podman build \
        --format docker \
        -t "$FULL_IMAGE" \
        --build-arg "AGENT_UID=$(id -u)" \
        -f "$dockerfile" \
        "$PROJECT_ROOT"

    trap - EXIT
    if [[ -n "$temp_ssh_key" && -f "$temp_ssh_key" ]]; then
        rm -f "$temp_ssh_key"
    fi

    log_ok "Image '$FULL_IMAGE' built successfully"
}
