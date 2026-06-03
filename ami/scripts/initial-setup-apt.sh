#!/usr/bin/env bash
# =============================================================================
# Bootstrap — Apt Probing & Installation
# =============================================================================
# Sourced by initial-setup.sh — not standalone
# =============================================================================

declare -A RESOLVED_PACKAGES=()
declare -A RESOLVED_STATUS=()

probe_apt_package() {
    local pkg="$1"

    if [[ -n "${RESOLVED_STATUS[$pkg]:-}" ]]; then
        return
    fi

    local pkg_info=""
    pkg_info=$(apt-cache show "$pkg" 2>/dev/null) || true  # silent-ok: pkg may not exist in apt repos, handled below

    if [[ -z "$pkg_info" ]]; then
        RESOLVED_STATUS[$pkg]="unavailable"
        return 0
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
        # Bootstrap entries (format: cmd|bootstrap|script) have no apt
        # package to probe.  Skipping them prevents probe_apt_package
        # from returning 1 (unavailable) and triggering set -e crash.
        if [[ "$entry" == *"|bootstrap|"* ]]; then
            continue
        fi
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

    # Detect if running under sudo — drop privileges for user-owned paths.
    local run_as_user=()
    if [[ -n "${SUDO_USER:-}" ]]; then
        run_as_user=("sudo" "-u" "$SUDO_USER")
    fi

    # Split bootstrap entries (|bootstrap| prefix) from apt entries
    local bootstrap_entries=()
    local apt_entries=()
    for entry in "${MISSING_ENTRIES[@]}"; do
        if [[ "$entry" == *"|bootstrap|"* ]]; then
            bootstrap_entries+=("$entry")
        else
            apt_entries+=("$entry")
        fi
    done

    # ------------------------------------------------------------------
    # Phase 1: Install apt packages FIRST so that tools needed by
    # bootstrap scripts (curl, wget, etc.) are already available.
    # ------------------------------------------------------------------
    if [[ ${#apt_entries[@]} -gt 0 ]]; then
        local apt_installable=()
        local unavail=()

        for entry in "${apt_entries[@]}"; do
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
        fi
    fi

    # ------------------------------------------------------------------
    # Phase 2: Run bootstrap scripts.
    # When running under sudo, drop to the calling user so that
    # .boot-linux/bin/ files are owned by the real user, not root.
    # ------------------------------------------------------------------
    if [[ ${#bootstrap_entries[@]} -gt 0 ]]; then
        for entry in "${bootstrap_entries[@]}"; do
            # 3 pipe-delimited fields: cmd|bootstrap|script_path
            IFS='|' read -r cmd _ script <<< "$entry"

            local script_path="${PROJECT_ROOT}/${script}"
            if [[ ! -f "$script_path" ]]; then
                log_error "✗ Bootstrap script not found: $script_path"
                log_error "  Run 'make ensure-repos' first to clone workspace sub-repos, then re-run init."
                return 1
            fi

            log_info "Bootstrapping $cmd..."
            if "${run_as_user[@]}" bash "$script_path"; then
                log_info "✓ $cmd bootstrapped successfully"
                # Post-install verification
                if find_binary "$cmd" &>/dev/null; then
                    log_ok "$cmd is now on PATH"
                else
                    log_warn "$cmd installed but not on PATH — reload your shell or check .boot-linux/bin/"
                fi
            else
                log_error "✗ $cmd bootstrap failed"
                return 1
            fi
        done
    fi

    local guard_script="${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_rust_guard.sh"
    if [[ -f "$guard_script" ]]; then
        bash "$guard_script" "reinstall"
    fi

    return 0
}
