#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# launch-mac.sh — Build and Launch WORKSPACE-VM Container on macOS
# =============================================================================
# Manages the workspace-vm-ubuntu container lifecycle with persistent restart
# policy. Supports shutdown, restart, and full recreation from scratch.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# =============================================================================
# Constants
# =============================================================================
CONTAINER_NAME="workspace-vm-ubuntu"
IMAGE_NAME="workspace-vm-ubuntu"
IMAGE_TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
VMS_DIR="${PROJECT_ROOT}/.vms"
VM_CONFIG="${PROJECT_ROOT}/workspace/config/vm-template.yaml"
HEALTHCHECK_TIMEOUT=300
HEALTHCHECK_POLL=2

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_ok()    { echo -e "${GREEN}  ✓${NC} $*"; }
log_section() { echo -e "\n${CYAN}${BOLD}═══ $* ═══${NC}\n"; }

# =============================================================================
# Argument Parsing
# =============================================================================
ACTION="launch"
VM_CONFIG_PATH="$VM_CONFIG"
FORCE_REBUILD=false

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Build and launch the WORKSPACE-VM container on macOS.

The container runs with --restart=always policy for persistence.

Options:
    --shutdown                  Stop and remove the container
    --restart                   Restart the running container
    --recreate-vm-from-scratch  Full rebuild: remove container, volumes, image
    --config <path>             Custom VM config (default: workspace/config/vm-template.yaml)
    --force-rebuild             Force image rebuild even if it exists
    -h, --help                  Show this help message

Examples:
    $(basename "$0")                            # Launch container (build if needed)
    $(basename "$0") --shutdown                 # Stop and remove container
    $(basename "$0") --restart                  # Restart running container
    $(basename "$0") --recreate-vm-from-scratch # Full clean rebuild
    $(basename "$0") --config my-vm.yaml        # Use custom config
    $(basename "$0") --force-rebuild            # Rebuild image even if exists
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --shutdown)
            ACTION="shutdown"
            shift
            ;;
        --restart)
            ACTION="restart"
            shift
            ;;
        --recreate-vm-from-scratch)
            ACTION="recreate"
            shift
            ;;
        --config)
            if [[ -z "${2:-}" ]]; then
                log_error "--config requires a path argument"
                exit 1
            fi
            VM_CONFIG_PATH="$2"
            shift 2
            ;;
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# =============================================================================
# Prerequisites Check
# =============================================================================
check_prerequisites() {
    log_section "Checking Prerequisites"

    local missing=()

    if ! command -v podman &>/dev/null; then
        log_error "podman not found"
        missing+=("podman")
    else
        log_ok "podman: $(podman --version)"
    fi

    if ! podman machine inspect podman-machine-default &>/dev/null; then
        log_error "podman machine not configured"
        missing+=("podman-machine")
    else
        log_ok "podman machine: configured"
    fi

    local machine_info_output
    if machine_info_output=$(podman machine info --format '{{.Host.CurrentMachine}}'); then
        if [[ -z "$machine_info_output" ]]; then
            log_error "podman machine not running"
            missing+=("podman-machine-running")
        else
            local machine_state
            machine_state=$(podman machine inspect --format '{{.State}}' podman-machine-default)
            if [[ "$machine_state" != "running" ]]; then
                log_error "podman machine not running (state: $machine_state)"
                missing+=("podman-machine-running")
            else
                log_ok "podman machine: running"
            fi
        fi
    else
        log_error "podman machine not running"
        missing+=("podman-machine-running")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing prerequisites: ${missing[*]}"
        log_info "Run ./workspace/scripts/install-mac.sh to install prerequisites"
        exit 1
    fi
}

# =============================================================================
# Shutdown Action
# =============================================================================
do_shutdown() {
    log_section "Shutting Down Container"

    if ! podman container exists "$CONTAINER_NAME"; then
        log_warn "Container '$CONTAINER_NAME' does not exist"
        return 0
    fi

    log_info "Stopping container '$CONTAINER_NAME'..."
    podman stop --time 10 "$CONTAINER_NAME"

    log_info "Removing container '$CONTAINER_NAME'..."
    podman rm -f --time 1 "$CONTAINER_NAME"

    log_ok "Container '$CONTAINER_NAME' shut down"
}

# =============================================================================
# Restart Action
# =============================================================================
do_restart() {
    log_section "Restarting Container"

    if ! podman container exists "$CONTAINER_NAME"; then
        log_warn "Container '$CONTAINER_NAME' does not exist"
        log_info "Launching new container..."
        do_launch
        return 0
    fi

    log_info "Restarting container '$CONTAINER_NAME'..."
    podman restart --time 10 "$CONTAINER_NAME"

    log_ok "Container '$CONTAINER_NAME' restarted"
    wait_for_healthy
    show_connection_info
}

# =============================================================================
# Recreate Action
# =============================================================================
do_recreate() {
    log_section "Recreating VM From Scratch"

    log_warn "This will remove the container, volumes, and image"

    do_shutdown

    log_info "Removing volumes..."
    for vol in workspace transcripts cache; do
        if podman volume exists "${CONTAINER_NAME}-${vol}"; then
            podman volume rm -f "${CONTAINER_NAME}-${vol}"
            log_info "  Removed volume: ${CONTAINER_NAME}-${vol}"
        fi
    done

    log_info "Removing image..."
    if podman image exists "$FULL_IMAGE"; then
        podman rmi "$FULL_IMAGE"
        log_info "  Removed image: $FULL_IMAGE"
    fi

    log_info "Cleaning up .vms directory..."
    if [[ -d "${VMS_DIR}" ]]; then
        rm -rf "${VMS_DIR:?}/"*
        log_info "  Cleaned: ${VMS_DIR}"
    fi

    log_ok "Full cleanup complete"
    log_info "Launching fresh container..."
    do_launch
}

# =============================================================================
# Password Management (defined in vm_credentials.sh)
# =============================================================================
source "${SCRIPT_DIR}/lib/vm_credentials.sh"

# =============================================================================
# Build Image (defined in vm_build_image.sh)
# =============================================================================
source "${SCRIPT_DIR}/lib/vm_build_image.sh"

# =============================================================================
# Create Volumes
# =============================================================================
create_volumes() {
    log_section "Creating Volumes"

    for vol in workspace transcripts cache; do
        local vol_name="${CONTAINER_NAME}-${vol}"
        if podman volume exists "$vol_name"; then
            log_ok "Volume '$vol_name' exists"
        else
            log_info "Creating volume '$vol_name'..."
            podman volume create "$vol_name"
            log_ok "Volume '$vol_name' created"
        fi
    done
}

# =============================================================================
# Create Network
# =============================================================================
create_network() {
    log_section "Creating Network"

    local network_name="workspace-vm-net"

    if podman network exists "$network_name"; then
        log_ok "Network '$network_name' exists"
    else
        log_info "Creating network '$network_name'..."
        podman network create "$network_name"
        log_ok "Network '$network_name' created"
    fi
}

# =============================================================================
# Launch Container
# =============================================================================
do_launch() {
    log_section "Launching Container"

    check_prerequisites

    if podman container exists "$CONTAINER_NAME"; then
        local state
        state=$(podman inspect --format '{{.State.Status}}' "$CONTAINER_NAME")
        if [[ "$state" == "running" ]]; then
            log_ok "Container '$CONTAINER_NAME' is already running"
            show_connection_info
            return 0
        elif [[ "$state" == "exited" ]] || [[ "$state" == "created" ]]; then
            log_info "Starting existing container '$CONTAINER_NAME'..."
            podman start "$CONTAINER_NAME"
            wait_for_healthy
            show_connection_info
            return 0
        fi
    fi

    build_image
    create_volumes
    create_network

    log_info "Creating container '$CONTAINER_NAME'..."

    podman run -d \
        --name "$CONTAINER_NAME" \
        --restart=always \
        --systemd=always \
        --label "workspace.type=vm" \
        --label "workspace.name=${CONTAINER_NAME}" \
        -p 8443:443 \
        -v "${CONTAINER_NAME}-workspace:/workspace" \
        -v "${CONTAINER_NAME}-transcripts:/transcripts" \
        -v "${CONTAINER_NAME}-cache:/cache" \
        --userns=keep-id \
        --memory 4g \
        --cpus 2 \
        --pids-limit 256 \
        --network workspace-vm-net \
        --cap-add NET_ADMIN \
        --health-on-failure=stop \
        "$FULL_IMAGE"

    log_ok "Container '$CONTAINER_NAME' created and started"
    wait_for_healthy
    show_connection_info
}

# =============================================================================
# Wait for Healthy
# =============================================================================
wait_for_healthy() {
    log_section "Waiting for Health Check"

    podman logs -f "$CONTAINER_NAME" &
    local logs_pid=$!
    trap "kill $logs_pid >/dev/null 2>&1" RETURN

    local deadline=$((SECONDS + HEALTHCHECK_TIMEOUT))
    local status="unknown"

    while [[ $SECONDS -lt $deadline ]]; do
        local status_raw
        if ! status_raw=$(podman inspect -f '{{.State.Health.Status}}' "$CONTAINER_NAME"); then
            status="unknown"
        else
            status="$status_raw"
        fi
        log_info "Health status: $status (elapsed: $((SECONDS))s)"

        if [[ "$status" == "healthy" ]]; then
            log_ok "Container is healthy"
            kill $logs_pid >/dev/null 2>&1
            return 0
        fi

        sleep "$HEALTHCHECK_POLL"
    done

    kill $logs_pid >/dev/null 2>&1
    log_error "Container did not become healthy within ${HEALTHCHECK_TIMEOUT}s (last status: $status)"
    return 1
}

# =============================================================================
# Show Connection Info
# =============================================================================
show_connection_info() {
    log_section "Connection Information"

    local container_ip
    container_ip=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NAME")

    log_info "Container: $CONTAINER_NAME"
    log_info "Image:     $FULL_IMAGE"

    local state
    state=$(podman inspect -f '{{.State.Status}}' "$CONTAINER_NAME")
    log_info "Status:    $state"

    if [[ -n "$container_ip" ]]; then
        log_info "IP:        $container_ip"
        log_info "URL:       https://${container_ip}:443 (via Traefik with mTLS)"
    fi

    local password
    password=$(get_password)
    if [[ -n "$password" ]]; then
        log_info ""
        log_info "Password:  $password"
        log_info "           (saved to: $PASSWORD_FILE)"
    fi

    log_info ""
    log_info "Useful commands:"
    log_info "  podman logs -f $CONTAINER_NAME        # Follow logs"
    log_info "  podman exec -it $CONTAINER_NAME bash  # Shell into container"
    log_info "  $(basename "$0") --restart             # Restart container"
    log_info "  $(basename "$0") --shutdown            # Stop container"
}

# =============================================================================
# Main
# =============================================================================
main() {
    log_section "WORKSPACE-VM Container Launcher (macOS)"

    case "$ACTION" in
        shutdown)
            do_shutdown
            ;;
        restart)
            do_restart
            ;;
        recreate)
            do_recreate
            ;;
        launch)
            do_launch
            ;;
        *)
            log_error "Unknown action: $ACTION"
            exit 1
            ;;
    esac
}

main "$@"
