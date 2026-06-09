#!/usr/bin/env bash
# AMI Orchestrator Banner - delegates to banner_helper.py for
# manifest-based extension discovery and rendering.

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[38;5;203m'
NC='\033[0m'

# Unset colors when --plain is active
for arg in "$@"; do
    if [[ "$arg" == "--plain" ]]; then
        GREEN=''
        BLUE=''
        RED=''
        NC=''
    fi
done

# Define quiet mode echo function
_ami_echo() {
    if [[ "$AMI_QUIET_MODE" != "1" ]]; then
        echo -e "$@"
    fi
}

# Function to display the banner
display_banner() {
    # Ignore any --exclude-categories args (rendering is now done in
    # Python via banner_helper.py which inspects manifests directly).
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --exclude-categories) shift ;;
        esac
        shift
    done

    _ami_echo "${GREEN}✓${NC} AMI Orchestrator shell environment configured successfully!"
    _ami_echo ""
    local banner_output
    banner_output=$(uv run python "$AMI_ROOT/workspace/utils/banner.py" --project-root "$AMI_ROOT")
    if [[ -n "$banner_output" ]]; then
        while IFS= read -r line; do
            _ami_echo " $line"
        done <<< "$banner_output"
    else
        _ami_echo "  OpenAMI"
    fi
    _ami_echo ""

    # Display extensions via Python helper (manifest-based discovery)
    local _banner_helper="$AMI_ROOT/workspace/scripts/shell/banner_helper.py"
    if [[ -f "$_banner_helper" ]]; then
        local _quiet_flag=""
        local _plain_flag=""
        [[ "$AMI_QUIET_MODE" == "1" ]] && _quiet_flag="--quiet"
        [[ -z "$GREEN" ]] && _plain_flag="--plain"
        uv run python "$_banner_helper" --mode banner $_quiet_flag $_plain_flag
    fi
}

# Function to display system status
display_system_status() {
    local sys_info_script="$AMI_ROOT/workspace/scripts/utils/sys_info.py"
    if [[ -f "$sys_info_script" ]]; then
        # Use uv run to ensure we have psutil available
        uv run python "$sys_info_script" 2>&1 || {
            # Fallback if uv not available
            echo -e "${BLUE}📊 Storage Status:${NC}"
            echo -e "  > Free space (root): $(df -h . | awk 'NR==2 {print $4}') available ($(df -h . | awk 'NR==2 {print $5}') used)"
            echo -e "  > Repository size:   $(du -sh . 2>&1 | awk '{print $1}')"
            echo -e ""
        }
    else
        echo -e "${BLUE}📊 Storage Status:${NC}"
        echo -e "  > Free space (root): $(df -h . | awk 'NR==2 {print $4}') available ($(df -h . | awk 'NR==2 {print $5}') used)"
        echo -e "  > Repository size:   $(du -sh . 2>&1 | awk '{print $1}')"
        echo -e ""
    fi
}

# Standalone invocation support
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ -z "${AMI_ROOT:-}" ]]; then
        echo "Error: AMI_ROOT not set" >&2
        exit 1
    fi
    display_banner "$@"
fi
