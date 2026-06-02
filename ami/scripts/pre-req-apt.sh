#!/usr/bin/env bash
# =============================================================================
# Bootstrap — Apt Probing & Installation
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

    # Bootstrap-type packages handled by their scripts
    if [[ "$pkg" == "gitleaks" ]]; then
        RESOLVED_PACKAGES[$pkg]="gitleaks — GitHub release binary"
        RESOLVED_STATUS[$pkg]="bootstrap"
        return 0
    fi

    local pkg_info=""
    pkg_info=$(apt-cache show "$pkg" 2>/dev/null) || true  # silent-ok: pkg may not exist in apt repos, handled below

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
        probe_apt_package "$pkg"
    done
}

install_missing() {
    if [[ ${#MISSING_ENTRIES[@]} -eq 0 ]]; then
        log_info "Nothing to install — all dependencies satisfied."
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
            gitleaks)
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
        log_error "No installable packages available."
        return 1
    fi

    local guard_script="${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_rust_guard.sh"
    if [[ -f "$guard_script" ]]; then
        bash "$guard_script" "install"
    fi

    return 0
}
