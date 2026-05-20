#!/usr/bin/env bash
# =============================================================================
# Pre-requisites — Apt Probing & Installation
# =============================================================================
# Sourced by pre-req.sh — not standalone
# =============================================================================

declare -A RESOLVED_PACKAGES=()
declare -A RESOLVED_STATUS=()

probe_apt_package() {
    local pkg="$1"

    if [[ -n "${RESOLVED_STATUS[$pkg]:-}" ]]; then
        return
    fi

    if [[ "$pkg" == "gcc-bootstrap" ]]; then
        RESOLVED_PACKAGES[$pkg]="GCC 15.1.0 (Dyne.org musl — direct download)"
        RESOLVED_STATUS[$pkg]="bootstrap"
        return 0
    fi
    if [[ "$pkg" == "gitleaks-bootstrap" ]]; then
        RESOLVED_PACKAGES[$pkg]="gitleaks — GitHub release binary (supply-chain verified)"
        RESOLVED_STATUS[$pkg]="bootstrap"
        return 0
    fi

    local pkg_info=""
    pkg_info=$(apt-cache show "$pkg" 2>/dev/null) || true  # silent-ok: package may not exist in apt, handled below

    if [[ -z "$pkg_info" ]]; then
        RESOLVED_STATUS[$pkg]="unavailable"
        return 1
    fi

    local version="" arch=""
    version=$(echo "$pkg_info" | grep -m1 "^Version:" | awk '{print $2}') || version=""
    arch=$(echo "$pkg_info" | grep -m1 "^Architecture:" | awk '{print $2}') || arch=""

    RESOLVED_PACKAGES[$pkg]="${version:-?} ${arch:-any}"
    RESOLVED_STATUS[$pkg]="available"
    return 0
}

probe_all_missing() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        return
    fi

    log_section "Probing apt for Available Packages"

    local unique_pkgs=()
    declare -A seen=()

    for entry in "${MISSING_ENTRIES[@]}"; do
        local pkg="${entry#*|}"
        pkg="${pkg%%|*}"
        if [[ -z "${seen[$pkg]:-}" ]]; then
            unique_pkgs+=("$pkg")
            seen[$pkg]=1
        fi
    done

    for pkg in "${unique_pkgs[@]}"; do
        if probe_apt_package "$pkg"; then
            log_probe "$pkg → ${RESOLVED_PACKAGES[$pkg]}"
        else
            log_probe "$pkg → ${RED}not available in apt${NC}"
            RESOLVED_STATUS[$pkg]="unavailable"
        fi
    done
}

install_missing() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        log_info "Nothing to install — all pre-requisites satisfied."
        return 0
    fi

    local apt_installable=()
    local bootstrap_installable=()
    local unavail=()

    for entry in "${MISSING_ENTRIES[@]}"; do
        local pkg="${entry#*|}"
        pkg="${pkg%%|*}"
        local status="${RESOLVED_STATUS[$pkg]:-unknown}"

        case "$status" in
            available)
                local already=false
                for existing in "${apt_installable[@]:-}"; do
                    [[ "$existing" == "$pkg" ]] && already=true && break
                done
                [[ "$already" == "false" ]] && apt_installable+=("$pkg")
                ;;
            bootstrap)
                bootstrap_installable+=("$pkg")
                ;;
            *)
                local already=false
                for existing in "${unavail[@]:-}"; do
                    [[ "$existing" == "$pkg" ]] && already=true && break
                done
                [[ "$already" == "false" ]] && unavail+=("$pkg")
                ;;
        esac
    done

    if [[ ${#unavail[@]} -gt 0 ]]; then
        log_warn "The following packages are not available:"
        for pkg in "${unavail[@]}"; do
            log_warn "  • $pkg"
        done
        log_warn "You may need to install these manually."
        echo ""
    fi

    for _bpkg in "${bootstrap_installable[@]:-}"; do
        case "$_bpkg" in
            gcc-bootstrap)
                log_info "Bootstrapping GCC/musl C compiler from direct download..."
                if bash "${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_gcc.sh"; then
                    log_info "✓ GCC/musl bootstrapped successfully"
                else
                    log_error "✗ GCC/musl bootstrap failed"
                    return 1
                fi
                ;;
            gitleaks-bootstrap)
                log_info "Bootstrapping gitleaks from GitHub release..."
                if bash "${PROJECT_ROOT}/projects/AMI-CI/scripts/bootstrap-gitleaks"; then
                    log_info "✓ gitleaks bootstrapped successfully"
                else
                    log_error "✗ gitleaks bootstrap failed"
                    return 1
                fi
                ;;
        esac
    done

    if [[ ${#apt_installable[@]} -gt 0 ]]; then
        log_info "Installing ${#apt_installable[@]} package(s) via apt: ${apt_installable[*]}"
        echo ""

        if sudo apt-get update -qq && sudo apt-get install -y "${apt_installable[@]}"; then
            echo ""
            log_info "${GREEN}${BOLD}Successfully installed: ${apt_installable[*]}${NC}"
        else
            echo ""
            log_error "Failed to install packages via apt."
            return 1
        fi
    elif [[ ${#bootstrap_installable[@]} -gt 0 ]]; then
        log_info "${GREEN}${BOLD}All missing dependencies resolved via bootstrap.${NC}"
    elif [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        :
    else
        log_error "No installable or bootstrappable packages available."
        return 1
    fi

    local guard_script="${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_rust_guard.sh"
    if [[ -f "$guard_script" ]]; then
        bash "$guard_script" "install"
    fi

    return 0
}
