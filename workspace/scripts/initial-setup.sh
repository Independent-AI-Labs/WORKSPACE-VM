#!/usr/bin/env bash
set -uo pipefail

# =============================================================================
# Bootstrap - install system dependencies and bootstrap tools.
# =============================================================================
# Usage:
#   sudo make bootstrap                       # install missing system deps
#   make bootstrap-check                      # check only, report missing
#
# Reads workspace/config/bootstrap-components.yaml as the single source of truth
# for what system dependencies and bootstrap scripts exist.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPONENTS_YAML="${PROJECT_ROOT}/workspace/config/bootstrap-components.yaml"

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
export_missing=false
install_only=false
[[ "$MODE" == "-install" ]] && install_mode=true
[[ "$MODE" == "-export-missing" ]] && export_missing=true
[[ "$MODE" == "-install-only" ]] && { install_only=true; install_mode=true; }

# =============================================================================
# Read dependency entries from YAML via inline Python
# =============================================================================
read_requires() {
    awk -F ': ' '
function emit(comp,    line) {
    if (etype == "type") {
        line = "type|" ekey "|" desc
        if (comp != "") line = line "|" comp
        print line
        if (ekey == "playwright-libs") pw_seen = 1
    } else if (etype == "cmd") {
        line = "cmd|" ekey "|" pkg "|" desc "|" boot "|" (opt == "" ? "False" : opt)
        if (comp != "") line = line "|" comp
        print line
    }
    etype = ekey = pkg = desc = boot = ""
    opt = "False"
    has_entry = 0
}

function kv(line) {
    sub(/^[ ]+/, "", line)
    if (!match(line, /: /)) { k = line; v = "" }
    else { k = substr(line, 1, RSTART-1); v = substr(line, RSTART+2) }
    gsub(/^['"'"'"]|['"'"'"]$/, "", v)
}

/^[[:space:]]*($|#)/ { next }

{
    match($0, /[^ ]/)
    indent = RSTART - 1
    raw = substr($0, RSTART)
    sub(/:$/, "", raw)
}

indent == 0 {
    if (has_entry && (mode == "top_req" || in_comp_req))
        emit(in_comp_req ? comp_name : "")
    has_entry = 0; in_comp = 0; in_comp_req = 0
    if (raw == "requires") mode = "top_req"
    else if (raw == "components") mode = "comp"
    else mode = ""
}

indent == 2 {
    sub(/^- /, "", raw)
    kv(raw)
    if (mode == "top_req") {
        if (has_entry) emit("")
        if (k == "check_cmd" || k == "check_type") {
            etype = (k == "check_cmd" ? "cmd" : "type"); ekey = v; has_entry = 1
        }
    } else if (mode == "comp") {
        if (has_entry && in_comp_req) emit(comp_name)
        has_entry = 0; in_comp = 1; in_comp_req = 0
        if (k == "name") comp_name = v
    }
}

indent == 4 {
    kv(raw)
    if (mode == "top_req") {
        if (k == "apt_package") pkg = v; else if (k == "description") desc = v
        else if (k == "bootstrap_script") boot = v; else if (k == "optional") opt = (v == "true" ? "True" : "False")
    } else if (mode == "comp" && in_comp) {
        if (k == "name") comp_name = v
        else if (k == "requires") { in_comp_req = 1; etype = ekey = pkg = desc = boot = ""; opt = "False" }
    }
}

indent == 6 {
    sub(/^- /, "", raw)
    kv(raw)
    if (mode == "comp" && in_comp && in_comp_req) {
        if (has_entry) emit(comp_name)
        if (k == "check_cmd" || k == "check_type") {
            etype = (k == "check_cmd" ? "cmd" : "type"); ekey = v; has_entry = 1
        }
    }
}

indent == 8 {
    kv(raw)
    if (mode == "comp" && in_comp && in_comp_req) {
        if (k == "apt_package") pkg = v; else if (k == "description") desc = v
        else if (k == "bootstrap_script") boot = v; else if (k == "optional") opt = (v == "true" ? "True" : "False")
    }
}

END {
    if (has_entry) emit(in_comp_req ? comp_name : "")
    if (!pw_seen) print "type|playwright-libs|Playwright browser dependencies"
}
' "$COMPONENTS_YAML"
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
    local cmd="$1" pkg="$2" desc="$3" optional="${4:-False}" bootstrap="${5:-}"
    local found_path="" version="" raw=""

    if found_path=$(find_binary "$cmd"); then
        raw=$("$found_path" -version 2>&1) || raw=""
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
    if [[ "$optional" == "True" ]]; then
        log_warn "$desc ${DIM}(optional - not found)${NC}"
        return 0
    else
        if [[ -n "$bootstrap" ]]; then
            log_miss "$desc ${DIM}(not found - bootstrap)${NC}"
            MISSING_ENTRIES+=("${cmd}|bootstrap|${bootstrap}")
        elif [[ -n "$pkg" ]]; then
            log_miss "$desc ${DIM}(not found - needs: $pkg)${NC}"
            MISSING_ENTRIES+=("${cmd}|${pkg}|${desc}")
        fi
        return 1
    fi
    fi
}

check_c_compiler() {
    local compilers=("gcc" "cc" "clang")
    for compiler in "${compilers[@]}"; do
        local found_path=""
        if found_path=$(find_binary "$compiler"); then
            local raw version
            raw=$("$found_path" -version 2>&1) || raw=""
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
    local _pw_lib_variants=(
        "libnss3"
        "libgbm1"
        "libatk-bridge2.0-0t64|libatk-bridge2.0-0"
        "libpango-1.0-0"
        "libcairo2"
        "libcups2t64|libcups2"
        "libdrm2"
        "libdbus-1-3"
        "libxkbcommon0"
        "libxrandr2"
    )
    local _pw_missing=0
    for entry in "${_pw_lib_variants[@]}"; do
        IFS='|' read -ra variants <<< "$entry"
        local installed=false

        for variant in "${variants[@]}"; do
            if dpkg -s "$variant" &>/dev/null 2>&1; then
                installed=true
                break
            fi
        done

        if [[ "$installed" == "true" ]]; then
            continue
        fi

        local available_pkg=""
        for variant in "${variants[@]}"; do
            if apt-cache show "$variant" &>/dev/null 2>&1; then
                available_pkg="$variant"
                break
            fi
        done

        if [[ -n "$available_pkg" ]]; then
            log_miss "Playwright library: ${variants[0]}"
            MISSING_ENTRIES+=("$available_pkg|$available_pkg|Playwright browser dependency ($available_pkg)")
        else
            log_miss "Playwright library: ${variants[0]} (not available in apt)"
        fi
        _pw_missing=1
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

check_libolm_headers() {
    local olm_h_paths=(
        "/usr/include/olm/olm.h"
        "/usr/local/include/olm/olm.h"
    )
    for h in "${olm_h_paths[@]}"; do
        if [[ -f "$h" ]]; then
            log_ok "libolm headers found at $h"
            return 0
        fi
    done
    log_miss "libolm development headers not found (needed to build python-olm)"
    MISSING_ENTRIES+=("libolm-dev|libolm-dev|libolm development headers (python-olm build dependency)")
    return 1
}

# =============================================================================
# Apt probing & install
# =============================================================================
# shellcheck source=initial-setup-apt.sh
if ! source "${SCRIPT_DIR}/initial-setup-apt.sh"; then
    echo "ERROR: failed to source initial-setup-apt.sh" >&2
    exit 1
fi

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
            if [[ -n "$check_cmd_val" ]]; then
                check_cmd "$check_cmd_val" "$apt_pkg" "$desc" "$optional" "$bootstrap"
            fi
            ;;
        type)
            IFS='|' read -r check_type_val desc comp_name <<< "$rest"
            case "$check_type_val" in
                c-compiler)  check_c_compiler ;;
                network-tools) check_network_tools ;;
                playwright-libs) check_playwright_libs ;;
                libolm-headers) check_libolm_headers ;;
            esac
            ;;
    esac
done < <(read_requires)

# Probe apt for missing
probe_all_missing

echo ""
log_section "Results"

if [[ "$export_missing" == "true" ]]; then
    MISSING_FILE="${TMPDIR:-/tmp}/ami-init-missing.$$.txt"
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        rm -f "$MISSING_FILE"
        log_info "${GREEN}${BOLD}All dependencies satisfied!${NC}"
        exit 0
    fi
    printf '%s\n' "${MISSING_ENTRIES[@]}" > "$MISSING_FILE"
    echo "$MISSING_FILE" > "${TMPDIR:-/tmp}/ami-init-missing.path"
    log_warn "${BOLD}Missing ${#MISSING_ENTRIES[@]} dependencies - wrote list for sudo install${NC}"
    exit 0
fi

if [[ "$install_only" == "true" ]]; then
    _pf="${TMPDIR:-/tmp}/ami-init-missing.path"
    MISSING_FILE=""
    if [[ -f "$_pf" ]]; then
        MISSING_FILE="$(< "$_pf")"
    fi
    if [[ -z "$MISSING_FILE" || ! -f "$MISSING_FILE" ]]; then
        log_info "No missing dependencies to install."
        exit 0
    fi
    MISSING_ENTRIES=()
    while IFS= read -r entry; do
        MISSING_ENTRIES+=("$entry")
    done < "$MISSING_FILE"
    rm -f "$MISSING_FILE" "${TMPDIR:-/tmp}/ami-init-missing.path"
    install_missing
    echo ""
    log_info "${GREEN}${BOLD}System dependencies installed.${NC}"
    exit 0
fi

if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
    log_info "${GREEN}${BOLD}All dependencies satisfied!${NC}"

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

echo ""
log_info "${GREEN}${BOLD}Initialization complete.${NC}"
log_info "Proceed with: ${BOLD}make install${NC}"
exit 0
