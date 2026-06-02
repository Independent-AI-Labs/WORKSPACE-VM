#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Bootstrap — install system dependencies and bootstrap tools.
# =============================================================================
# Usage:
#   sudo make bootstrap                       # install missing system deps
#   make bootstrap-check                      # check only, report missing
#
# Reads ami/config/bootstrap-components.yaml as the single source of truth
# for what system dependencies and bootstrap scripts exist.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPONENTS_YAML="${PROJECT_ROOT}/ami/config/bootstrap-components.yaml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_ok()    { echo -e "${GREEN}  ✓${NC} $*"; }
log_miss()  { echo -e "${RED}  ✗${NC} $*"; }
log_section() { echo -e "\n${CYAN}${BOLD}═══ $* ═══${NC}\n"; }

MODE="${1:-check}"
install_mode=false
[[ "$MODE" == "--install" ]] && install_mode=true

# =============================================================================
# Read dependency entries from YAML via inline Python
# =============================================================================
read_requires() {
    python3 - "$COMPONENTS_YAML" <<'PYEOF'
import sys

yaml_path = sys.argv[1]

with open(yaml_path) as f:
    text = f.read()

entries = []

def emit_entry(entry_dict, comp_name=None):
    """Output one dependency entry as a pipe-delimited line."""
    check_cmd = entry_dict.get("check_cmd", "")
    check_type = entry_dict.get("check_type", "")
    apt_pkg = entry_dict.get("apt_package", "")
    bootstrap = entry_dict.get("bootstrap_script", "")
    desc = entry_dict.get("description", "")
    optional = str(entry_dict.get("optional", False)).lower() == "true"

    if check_type:
        line = f"type|{check_type}|{desc}"
        if comp_name:
            line = f"{line}|{comp_name}"
        entries.append(line)
    elif check_cmd:
        line = f"cmd|{check_cmd}|{apt_pkg}|{desc}|{bootstrap}|{optional}"
        if comp_name:
            line = f"{line}|{comp_name}"
        entries.append(line)


# State machine
in_top_requires = False
in_components = False
in_component = False
in_component_requires = False
current_component = ""
current_entry = {}
entry_indent = -1

for raw in text.splitlines():
    line = raw.rstrip()
    if not line or line.lstrip().startswith("#"):
        continue
    indent = len(line) - len(line.lstrip())
    stripped = line.strip().rstrip(":")

    # Top-level keys
    if indent == 0:
        if current_entry and (in_top_requires or in_component_requires):
            emit_entry(current_entry, current_component if in_component_requires else None)
            current_entry = {}
        in_top_requires = (stripped == "requires")
        in_components = (stripped == "components")
        in_component = False
        in_component_requires = False
        continue

    # Top-level requires entries at indent 2
    if in_top_requires and indent == 2 and stripped.startswith("- "):
        if current_entry:
            emit_entry(current_entry)
            current_entry = {}
        entry_indent = indent
        key = stripped[2:].strip()
        if ":" in key:
            k, v = key.split(":", 1)
            current_entry[k.strip()] = v.strip().strip("'\"")
        continue

    # Top-level requires field at indent 4
    if in_top_requires and indent == 4 and not stripped.startswith("- "):
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            current_entry[k.strip()] = v.strip().strip("'\"")
        continue

    # Component entries at indent 2
    if in_components and indent == 2 and stripped.startswith("- "):
        # Emit component-level requires before moving to next component
        if current_entry and in_component_requires:
            emit_entry(current_entry, current_component)
            current_entry = {}
        in_component = True
        in_component_requires = False
        current_component = ""
        continue

    # Component field at indent 4
    if in_component and indent == 4 and not stripped.startswith("- "):
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k == "name":
                current_component = v.strip("'\"")
            elif k == "requires":
                in_component_requires = True
                current_entry = {}
        continue

    # Component requires entries at indent 6
    if in_component and in_component_requires and indent == 6 and stripped.startswith("- "):
        if current_entry:
            emit_entry(current_entry, current_component)
            current_entry = {}
        key = stripped[2:].strip()
        if ":" in key:
            k, v = key.split(":", 1)
            current_entry[k.strip()] = v.strip().strip("'\"")
        continue

    # Component requires field at indent 8
    if in_component and in_component_requires and indent == 8:
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            current_entry[k.strip()] = v.strip().strip("'\"")
        continue

# Emit last entry
if current_entry:
    comp = current_component if in_component_requires else None
    emit_entry(current_entry, comp)

# Emit hardcoded playwright-libs if not already present
has_playwright = any("playwright-libs" in e for e in entries)
if not has_playwright:
    entries.append("type|playwright-libs|Playwright browser dependencies")

for e in entries:
    print(e)
PYEOF
}

# =============================================================================
# Binary finding
# =============================================================================
SYSTEM_PATHS="/usr/bin /usr/sbin /usr/local/bin /usr/local/sbin /snap/bin"

find_binary() {
    local cmd="$1"
    if command -v "$cmd" &> /dev/null; then
        command -v "$cmd"
        return 0
    fi
    for dir in $SYSTEM_PATHS; do
        if [[ -x "${dir}/${cmd}" ]]; then
            echo "${dir}/${cmd}"
            return 0
        fi
    done
    if [[ -x "${PROJECT_ROOT}/.boot-linux/bin/${cmd}" ]]; then
        echo "${PROJECT_ROOT}/.boot-linux/bin/${cmd}"
        return 0
    fi
    return 1
}

first_line() { local _out; _out="$1"; echo "${_out%%$'\n'*}"; }

# =============================================================================
# Check functions
# =============================================================================
check_cmd() {
    local cmd="$1" pkg="$2" desc="$3"
    local found_path="" version="" raw=""

    if found_path=$(find_binary "$cmd"); then
        raw=$("$found_path" --version 2>&1) || raw=""
        version=$(first_line "$raw" | cut -c1-60)
        [[ -z "$version" ]] && { raw=$("$found_path" -V 2>&1) || raw=""; version=$(first_line "$raw" | cut -c1-60); }
        [[ -z "$version" ]] && { raw=$("$found_path" version 2>&1) || raw=""; version=$(first_line "$raw" | cut -c1-60); }
        if [[ -n "$version" ]]; then
            log_ok "$desc ${DIM}($version)${NC}"
        else
            log_ok "$desc ${DIM}(found at $found_path)${NC}"
        fi
        return 0
    else
        log_miss "$desc ${DIM}(not found — needs: $pkg)${NC}"
        [[ -n "$pkg" ]] && MISSING_ENTRIES+=("${cmd}|${pkg}|${desc}")
        return 1
    fi
}

check_c_compiler() {
    local compilers=("gcc" "cc" "clang")
    for compiler in "${compilers[@]}"; do
        local found_path=""
        if found_path=$(find_binary "$compiler"); then
            local raw version
            raw=$("$found_path" --version 2>&1) || raw=""
            version=$(first_line "$raw" | cut -c1-60)
            log_ok "C compiler: $version"
            return 0
        fi
    done
    log_miss "No C compiler found (need gcc, cc, or clang)"
    MISSING_ENTRIES+=("gcc|gcc|C compiler (gcc/cc/clang)")
    return 1
}

check_playwright_libs() {
    local _pw_libs=(libnss3 libgbm1 libatk-bridge2.0-0t64 libpango-1.0-0 libcairo2 libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 libxrandr2)
    local _pw_missing=0
    for lib in "${_pw_libs[@]}"; do
        if dpkg -s "$lib" &>/dev/null 2>&1; then
            :
        else
            log_miss "Playwright library: $lib"
            MISSING_ENTRIES+=("$lib|$lib|Playwright browser dependency ($lib)")
            _pw_missing=1
        fi
    done
    [[ $_pw_missing -eq 0 ]] && log_ok "Playwright system libraries"
}

check_network_tools() {
    if ! find_binary curl &>/dev/null && ! find_binary wget &>/dev/null; then
        log_miss "Neither curl nor wget found (need at least one)"
        MISSING_ENTRIES+=("curl|curl|curl or wget")
    else
        find_binary curl &>/dev/null && log_ok "curl available"
        find_binary wget &>/dev/null && log_ok "wget available"
    fi
}

# =============================================================================
# Apt probing & install
# =============================================================================
# shellcheck source=pre-req-apt.sh
source "${SCRIPT_DIR}/pre-req-apt.sh"

# =============================================================================
# Main
# =============================================================================
declare -a MISSING_ENTRIES=()

log_section "System Pre-requisites"
log_info "Project: ${PROJECT_ROOT}"
echo ""

# Read dependency entries from YAML
log_section "Checking Dependencies"
while IFS='|' read -r entry_type rest; do
    case "$entry_type" in
        cmd)
            IFS='|' read -r check_cmd_val apt_pkg desc bootstrap optional comp_name <<< "$rest"
            [[ -n "$check_cmd_val" ]] && check_cmd "$check_cmd_val" "$apt_pkg" "$desc"
            ;;
        type)
            IFS='|' read -r check_type_val desc comp_name <<< "$rest"
            case "$check_type_val" in
                c-compiler)  check_c_compiler ;;
                network-tools) check_network_tools ;;
                playwright-libs) check_playwright_libs ;;
            esac
            ;;
    esac
done < <(read_requires)

# Probe apt for missing
probe_all_missing

echo ""
log_section "Results"

if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
    log_info "${GREEN}${BOLD}All dependencies satisfied!${NC}"

    # Run rust guard install
    guard_script="${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_rust_guard.sh"
    if [[ -f "$guard_script" ]]; then
        echo ""
        bash "$guard_script" "install"
    fi

    echo ""
    log_info "Proceed with: ${BOLD}make install${NC}"
    exit 0
fi

if [[ "$install_mode" == "false" ]]; then
    log_warn "${BOLD}Missing ${#MISSING_ENTRIES[@]} dependencies:${NC}"
    echo ""
    for entry in "${MISSING_ENTRIES[@]}"; do
        IFS='|' read -r cmd pkg desc <<< "$entry"
        echo -e "  ${RED}✗${NC} $desc (needs: $pkg)"
    done
    echo ""
    log_info "Run: ${BOLD}sudo make bootstrap${NC}"
    exit 1
fi

# Install mode
install_missing
