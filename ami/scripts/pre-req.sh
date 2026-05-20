#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Pre-requisites Check & Installation Script
# =============================================================================
# Usage:
#   ./pre-req.sh [--install|--ci|--uninstall-rust-guard|--reinstall-rust-guard|--check-rust-guard]
#
# Called by: make pre-req-check (via make install / make install-ci)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

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
log_probe() { echo -e "${CYAN}  →${NC} $*"; }
log_section() { echo -e "\n${CYAN}${BOLD}═══ $* ═══${NC}\n"; }

MODE="interactive"
RUST_GUARD_ACTION=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --install|-i) MODE="install";  shift ;;
        --ci)         MODE="ci";       shift ;;
        --check-rust-guard)   RUST_GUARD_ACTION="check"; shift ;;
        --uninstall-rust-guard) RUST_GUARD_ACTION="uninstall"; shift ;;
        --reinstall-rust-guard) RUST_GUARD_ACTION="reinstall"; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install, -i           Auto-install missing dependencies (requires sudo)"
            echo "  --ci                    CI mode: check only, exit 1 if missing"
            echo "  --check-rust-guard       Check rust guard installation status"
            echo "  --uninstall-rust-guard   Remove SUID guard, restore system git"
            echo "  --reinstall-rust-guard   Force reinstall rust guard"
            echo "  --help, -h              Show this help message"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -n "$RUST_GUARD_ACTION" ]]; then
    RUST_GUARD_SCRIPT="${SCRIPT_DIR}/bootstrap/bootstrap_rust_guard.sh"
    if [[ ! -f "$RUST_GUARD_SCRIPT" ]]; then
        log_error "Rust guard bootstrap script not found at $RUST_GUARD_SCRIPT"
        exit 1
    fi
    exec bash "$RUST_GUARD_SCRIPT" "$RUST_GUARD_ACTION"
fi

declare -a MISSING_ENTRIES=()

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

check_command() {
    local cmd="$1"
    local package="$2"
    local description="$3"

    local found_path=""
    if found_path=$(find_binary "$cmd"); then
        local version="" raw=""
        raw=$("$found_path" --version 2>&1) || raw=""
        version=$(first_line "$raw" | cut -c1-60)
        if [[ -z "$version" ]]; then
            raw=$("$found_path" -V 2>&1) || raw=""
            version=$(first_line "$raw" | cut -c1-60)
        fi
        if [[ -z "$version" ]]; then
            raw=$("$found_path" version 2>&1) || raw=""
            version=$(first_line "$raw" | cut -c1-60)
        fi
        if [[ -n "$version" ]]; then
            log_ok "$description ${DIM}($version)${NC}"
        else
            log_ok "$description ${DIM}(found at $found_path)${NC}"
        fi
    else
        log_miss "$description ${DIM}(not found — needs: $package)${NC}"
        MISSING_ENTRIES+=("${cmd}|${package}|${description}")
    fi
}

check_c_compiler() {
    local compilers=("gcc" "cc" "clang")

    for compiler in "${compilers[@]}"; do
        local found_path=""
        if found_path=$(find_binary "$compiler"); then
            local version raw
            raw=$("$found_path" --version 2>&1) || raw=""
            version=$(first_line "$raw" | cut -c1-60)
            log_ok "C compiler: $version"
            return 0
        fi
    done

    log_miss "No C compiler found (need gcc, cc, or clang)"
    MISSING_ENTRIES+=("gcc|gcc-bootstrap|C compiler (gcc/cc/clang)")
    return 1
}

check_playwright() {
    log_section "Browser Automation (Playwright)"
    local _pw_missing=0
    local _pw_libs=(libnss3 libgbm1 libatk-bridge2.0-0t64 libpango-1.0-0 libcairo2 libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 libxrandr2)
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
    log_section "Network Tools"
    if ! find_binary curl &>/dev/null && ! find_binary wget &>/dev/null; then
        log_miss "Neither curl nor wget found (need at least one)"
        local _already=false
        for entry in "${MISSING_ENTRIES[@]:-}"; do
            [[ "$entry" == curl\|* ]] && { _already=true; break; }
        done
        [[ "$_already" == "false" ]] && MISSING_ENTRIES+=("curl|curl|curl or wget")
    else
        find_binary curl &>/dev/null && log_ok "curl available"
        find_binary wget &>/dev/null && log_ok "wget available"
    fi
}

prompt_install() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        return 0
    fi

    echo ""
    log_warn "${BOLD}Missing ${#MISSING_ENTRIES[@]} package(s):${NC}"
    echo ""

    for entry in "${MISSING_ENTRIES[@]}"; do
        IFS='|' read -r cmd pkg desc <<< "$entry"
        local resolved="${RESOLVED_PACKAGES[$pkg]:-not available}"
        local status="${RESOLVED_STATUS[$pkg]:-unknown}"
        if [[ "$status" == "available" ]]; then
            echo -e "  ${RED}✗${NC} $desc"
            echo -e "    ${DIM}apt package: $pkg ($resolved)${NC}"
        elif [[ "$status" == "bootstrap" ]]; then
            echo -e "  ${RED}✗${NC} $desc"
            echo -e "    ${CYAN}bootstrap: $resolved (no sudo needed)${NC}"
        else
            echo -e "  ${RED}✗${NC} $desc"
            echo -e "    ${RED}not available — install manually${NC}"
        fi
    done

    echo ""

    local any_installable=false
    for entry in "${MISSING_ENTRIES[@]}"; do
        local pkg="${entry#*|}"
        pkg="${pkg%%|*}"
        local status="${RESOLVED_STATUS[$pkg]:-}"
        if [[ "$status" == "available" || "$status" == "bootstrap" ]]; then
            any_installable=true
            break
        fi
    done

    if [[ "$any_installable" == "false" ]]; then
        log_error "None of the missing packages are available in apt."
        log_error "Install them manually, then retry: make install"
        return 1
    fi

    if [[ "$MODE" == "interactive" ]] && [[ -t 0 ]]; then
        echo -ne "${CYAN}${BOLD}Auto-install missing packages using sudo? [y/N] ${NC}"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY])
                echo ""
                install_missing
                return $?
                ;;
            *)
                echo ""
                log_info "Skipping auto-install."
                log_info "To install later, run: ${BOLD}sudo make pre-req${NC}"
                return 1
                ;;
        esac
    else
        log_info "To install missing packages, run:"
        log_info "${BOLD}  sudo make pre-req${NC}"
        return 1
    fi
}

# =============================================================================
# Apt Probing & Installation (sourced from sub-file)
# =============================================================================
# shellcheck source=pre-req-apt.sh
source "${SCRIPT_DIR}/pre-req-apt.sh"

# =============================================================================
# Main Check Phase
# =============================================================================

log_section "System Pre-requisites Check"
log_info "Project: ${PROJECT_ROOT}"
echo ""

log_section "Core Build Tools"
check_command "make" "make" "GNU Make" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "curl" "curl" "curl" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_c_compiler || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES

log_section "System Dependencies"
check_command "git" "git" "Git version control" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "ssh" "openssh-client" "OpenSSH client" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "sshd" "openssh-server" "OpenSSH server" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "openssl" "openssl" "OpenSSL toolkit" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "openvpn" "openvpn" "OpenVPN client" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES

log_section "Additional Tools"
check_command "tar" "tar" "tar archiver" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "gzip" "gzip" "gzip compression" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "dpkg-deb" "dpkg" "dpkg-deb extractor" || true  # silent-ok: non-fatal check, accumulates MISSING_ENTRIES
check_command "gitleaks" "gitleaks-bootstrap" "Gitleaks (secret scanning)"

check_playwright
check_network_tools

probe_all_missing

echo ""
log_section "Check Results"

if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
    log_info "${GREEN}${BOLD}All pre-requisites are satisfied!${NC}"

    if [[ "$MODE" == "install" ]]; then
        guard_script="${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_rust_guard.sh"
        if [[ -f "$guard_script" ]]; then
            echo ""
            bash "$guard_script" "install"
        fi
    fi

    echo ""
    log_info "You can proceed with: ${BOLD}make install${NC}"
    exit 0
fi

case "$MODE" in
    ci)
        log_error "${BOLD}Missing ${#MISSING_ENTRIES[@]} package(s) — CI mode, failing.${NC}"
        echo ""
        for entry in "${MISSING_ENTRIES[@]}"; do
            IFS='|' read -r cmd pkg desc <<< "$entry"
            echo -e "  ${RED}✗${NC} $desc (needs: $pkg)"
        done
        echo ""
        log_error "Run: sudo make pre-req"
        exit 1
        ;;
    install)
        install_missing
        exit $?
        ;;
    interactive|*)
        prompt_install
        exit $?
        ;;
esac
