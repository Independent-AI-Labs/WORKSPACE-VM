#!/usr/bin/env bash
# Bootstrap: Build and install SUID git guard
# Called by: pre-req.sh (after apt dependencies installed)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

MODE="${1:-install}"  # install | uninstall | reinstall | check

divert_is_active() {
    dpkg-divert --list /usr/bin/git | grep -q 'git.distrib'
}

uninstall_guard() {
    log_info "Uninstalling git guard..."
    if command -v chattr >/dev/null && [[ -f /usr/bin/git ]]; then
        chattr -i /usr/bin/git
    fi
    rm -f /usr/bin/git
    if divert_is_active; then
        dpkg-divert --rename --remove /usr/bin/git
        log_info "Removed dpkg-divert"
    fi
    if [[ -f /usr/bin/git.original ]]; then
        if command -v chattr >/dev/null; then
            chattr -i /usr/bin/git.original
        fi
        mv /usr/bin/git.original /usr/bin/git
        chown root:root /usr/bin/git
        chmod 0755 /usr/bin/git
        log_info "Restored /usr/bin/git from git.original"
    elif [[ -f /usr/bin/git.distrib ]]; then
        mv /usr/bin/git.distrib /usr/bin/git
        chown root:root /usr/bin/git
        chmod 0755 /usr/bin/git
        log_info "Restored /usr/bin/git from git.distrib"
    else
        log_error "No git backup found — cannot restore"
        log_error "Reinstall git: sudo apt install --reinstall git"
        return 1
    fi
    rm -f /etc/apt/apt.conf.d/99git-guard
    log_info "Git guard uninstalled — /usr/bin/git restored"
    git --version
}

rollback_guard() {
    log_warn "Installation failed — rolling back..."
    if command -v chattr >/dev/null && [[ -f /usr/bin/git ]]; then
        chattr -i /usr/bin/git
    fi
    rm -f /usr/bin/git
    if divert_is_active; then
        dpkg-divert --rename --remove /usr/bin/git
    fi
    if [[ -f /usr/bin/git.original ]]; then
        if command -v chattr >/dev/null; then
            chattr -i /usr/bin/git.original
        fi
        mv /usr/bin/git.original /usr/bin/git
        chown root:root /usr/bin/git
        chmod 0755 /usr/bin/git
        log_info "Restored /usr/bin/git from git.original"
    fi
}

preflight_check() {
    if [[ -f /usr/bin/git.original ]]; then
        local gmode gowner
        gmode=$(stat -c '%a' /usr/bin/git.original)
        gowner=$(stat -c '%U:%G' /usr/bin/git.original)
        if [[ "$gmode" == "755" && "$gowner" == "root:root" ]]; then
            if [[ -x /usr/bin/git ]]; then
                local guard_mode
                guard_mode=$(stat -c '%a' /usr/bin/git)
                if [[ "$guard_mode" == "4555" ]]; then
                    log_info "Git guard is already installed."
                    return 0
                fi
            fi
        fi
    fi
    return 1
}

install_guard() {
    echo ""
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD} Git Guard Installation (SUID-root)${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
    echo ""
    echo "This will:"
    echo "  - Build the ami-git-guard Rust binary from source"
    echo "  - Relocate /usr/bin/git -> /usr/bin/git.original (0755 root-owned)"
    echo "  - Install the guard as /usr/bin/git (4555 SUID root)"
    echo "  - Configure dpkg-divert to protect from apt overwrites"
    echo "  - Remove previous .boot-linux/bin/git wrapper"
    echo "  - Set immutable attributes on the guard binary"
    echo "  - Register apt post-invoke hook for change detection"
    echo ""
    echo "After installation, ONLY the SUID guard can invoke real git."
    echo "To uninstall: sudo make pre-req --uninstall-git-guard"
    echo ""

    if [[ -t 0 ]] && [[ "$MODE" == "install" ]]; then
        echo -ne "${CYAN}${BOLD}Proceed with git guard installation? [y/N] ${NC}"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY]) ;;
            *) log_info "Git guard installation cancelled."; return 0 ;;
        esac
    fi

    # Phase 1: Build Rust binary
    log_info "Building ami-git-guard Rust binary..."

    local rust_boot_dir="${PROJECT_ROOT}/.boot-linux"
    local rust_bin_dir="${rust_boot_dir}/bin"
    local rustc_bin=""
    local cargo_bin=""
    local rustup_bin=""

    # Detect rust: bootstrapped first, then system
    if [[ -x "${rust_bin_dir}/rustc" && -x "${rust_bin_dir}/cargo" ]]; then
        rustc_bin="${rust_bin_dir}/rustc"
        cargo_bin="${rust_bin_dir}/cargo"
        rustup_bin="${rust_bin_dir}/rustup"
        log_info "Using bootstrapped Rust from ${rust_bin_dir}"
    elif command -v rustc >/dev/null && command -v cargo >/dev/null; then
        rustc_bin="$(command -v rustc)"
        cargo_bin="$(command -v cargo)"
        if command -v rustup >/dev/null; then
            rustup_bin="$(command -v rustup)"
        fi
        log_info "Using system Rust: ${rustc_bin}"
    else
        log_warn "Rust toolchain not found. Installing via rustup..."
        bash "${PROJECT_ROOT}/ami/scripts/bootstrap/bootstrap_rust.sh" || {
            log_error "Rust installation failed"
            return 1
        }
        if [[ ! -x "${rust_bin_dir}/rustc" || ! -x "${rust_bin_dir}/cargo" ]]; then
            log_error "Rust binaries missing after bootstrap"
            return 1
        fi
        rustc_bin="${rust_bin_dir}/rustc"
        cargo_bin="${rust_bin_dir}/cargo"
        rustup_bin="${rust_bin_dir}/rustup"
        log_info "Using bootstrapped Rust from ${rust_bin_dir}"
    fi

    local guard_dir="${PROJECT_ROOT}/projects/ami-git-guard"
    if [[ ! -f "$guard_dir/Cargo.toml" ]]; then
        log_error "Rust project not found at $guard_dir"
        return 1
    fi

    cd "$guard_dir"
    local guard_bin=""
    local build_musl=0

    if [[ -n "$rustup_bin" && -x "$rustup_bin" ]]; then
        local installed_targets
        installed_targets=$(RUSTUP_HOME="${rust_boot_dir}/rust" CARGO_HOME="${rust_boot_dir}/rust" "$rustup_bin" target list --installed)
        if echo "$installed_targets" | grep -q musl; then
            build_musl=1
        fi
    fi

    # Build with system PATH first so gcc finds system ld, then append rust bin dir
    # for cargo to locate rustc. Must NOT put rust_bin_dir before /usr/bin.
    local build_path="/usr/local/bin:/usr/bin:/usr/sbin:/bin:/sbin:${rust_bin_dir}"
    if [[ "$build_musl" -eq 1 ]]; then
        log_info "Building statically linked binary (musl)..."
        RUSTUP_HOME="${rust_boot_dir}/rust" \
        CARGO_HOME="${rust_boot_dir}/rust" \
        PATH="$build_path" \
        CC=/usr/bin/gcc \
        RUSTFLAGS="-C linker=/usr/bin/gcc" \
        "$cargo_bin" build --release --target x86_64-unknown-linux-musl
        guard_bin="target/x86_64-unknown-linux-musl/release/ami-git-guard"
    else
        log_info "Building dynamically linked binary (gnu)..."
        RUSTUP_HOME="${rust_boot_dir}/rust" \
        CARGO_HOME="${rust_boot_dir}/rust" \
        PATH="$build_path" \
        CC=/usr/bin/gcc \
        RUSTFLAGS="-C linker=/usr/bin/gcc" \
        "$cargo_bin" build --release
        guard_bin="target/release/ami-git-guard"
    fi

    if [[ ! -f "$guard_bin" ]]; then
        log_error "Build failed — binary not found at $guard_bin"
        return 1
    fi
    if ! file "$guard_bin" | grep -q ELF; then
        log_error "Build produced invalid ELF binary"
        return 1
    fi
    if [[ ! -s "$guard_bin" ]]; then
        log_error "Build produced empty binary"
        return 1
    fi
    log_info "Build successful: $(file "$guard_bin" | cut -d: -f2)"

    # Phase 2: Skip system install if guard is already installed and binary is identical
    if [[ -f /usr/bin/git.original && -x /usr/bin/git ]]; then
        local installed_hash built_hash
        installed_hash=$(sha256sum /usr/bin/git | awk '{print $1}')
        built_hash=$(sha256sum "$guard_bin" | awk '{print $1}')
        if [[ "$installed_hash" == "$built_hash" ]]; then
            log_info "Guard binary is up to date — skipping system installation"
            return 0
        fi
    fi

    # Phase 4: Detect bypass vectors
    for path in /snap/bin/git /usr/local/bin/git; do
        if [[ -x "$path" ]]; then
            log_warn "Alternative git found at $path — this bypasses the guard"
        fi
    done

    # Phase 5: Divert + relocate git
    if [[ ! -x /usr/bin/git ]]; then
        log_error "System git not found at /usr/bin/git"
        return 1
    fi

    # Copy to git.original first (only on first install — never overwrite existing backup)
    if [[ ! -f /usr/bin/git.original ]]; then
        cp /usr/bin/git /usr/bin/git.original
        chown root:root /usr/bin/git.original
        chmod 0755 /usr/bin/git.original

        local orig_hash copy_hash
        orig_hash=$(sha256sum /usr/bin/git | awk '{print $1}')
        copy_hash=$(sha256sum /usr/bin/git.original | awk '{print $1}')
        if [[ "$orig_hash" != "$copy_hash" ]]; then
            log_error "Checksum mismatch — git.original does not match"
            rm -f /usr/bin/git.original
            return 1
        fi
    fi

    # Configure dpkg-divert
    if divert_is_active; then
        log_warn "dpkg-divert already in place — continuing"
    else
        dpkg-divert --local --divert /usr/bin/git.distrib --rename --add /usr/bin/git
    fi

    # Install guard binary (temporarily remove immutability if present)
    if command -v chattr >/dev/null && [[ -f /usr/bin/git ]]; then
        chattr -i /usr/bin/git
    fi
    cp "$guard_bin" /usr/bin/git
    chown root:root /usr/bin/git
    chmod 4555 /usr/bin/git

    # Set immutable attribute
    if command -v chattr >/dev/null; then
        chattr +i /usr/bin/git || log_warn "Could not set immutable on /usr/bin/git"
        chattr +i /usr/bin/git.original || log_warn "Could not set immutable on /usr/bin/git.original"
    else
        log_warn "chattr not available — skipping immutable attributes"
    fi

    # Remove previous bash wrapper
    if [[ -f "$PROJECT_ROOT/.boot-linux/bin/git" ]]; then
        rm -f "$PROJECT_ROOT/.boot-linux/bin/git"
        log_info "Removed previous bash wrapper at .boot-linux/bin/git"
    fi
    hash -r

    # Restrict alternate git binaries
    for path in /snap/bin/git /usr/local/bin/git; do
        if [[ -x "$path" ]]; then
            chmod 000 "$path"
            log_info "Restricted $path (bypass vector)"
        fi
    done

    # Register apt post-invoke hook
    # Apt config syntax: no shell redirections allowed inside DPkg::Post-Invoke
    # We write a helper script and invoke it from the apt config
    cat > /etc/apt/apt.conf.d/99git-guard << 'EOF'
DPkg::Post-Invoke { "/usr/lib/ami-git-guard/apt-check.sh"; };
EOF
    mkdir -p /usr/lib/ami-git-guard
    cat > /usr/lib/ami-git-guard/apt-check.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
if dpkg -l git | grep -q '^ii' && [[ ! -f /usr/bin/git.original ]]; then
    echo '[WARN] Git package changed but git guard not detected. Re-run: sudo make pre-req' >&2
fi
EOF
    chmod 755 /usr/lib/ami-git-guard/apt-check.sh

    # Create audit log directory
    mkdir -p /var/log/ami-git-guard
    chmod 1777 /var/log/ami-git-guard

    # Verification
    echo ""
    log_info "Running post-installation verification..."

    local errors=0
    local guard_mode guard_owner
    guard_mode=$(stat -c '%a' /usr/bin/git)
    guard_owner=$(stat -c '%U:%G' /usr/bin/git)
    if [[ "$guard_mode" != "4555" || "$guard_owner" != "root:root" ]]; then
        log_error "Guard binary has wrong permissions: $guard_mode $guard_owner"
        errors=1
    fi

    local real_mode real_owner
    real_mode=$(stat -c '%a' /usr/bin/git.original)
    real_owner=$(stat -c '%U:%G' /usr/bin/git.original)
    if [[ "$real_mode" != "755" || "$real_owner" != "root:root" ]]; then
        log_error "git.original has wrong permissions: $real_mode $real_owner"
        errors=1
    fi

    if [[ -n "${SUDO_USER:-}" ]]; then
        if sudo -u "$SUDO_USER" git --version; then
            log_info "git --version: $(git --version)"
        else
            log_error "git --version failed"
            errors=1
        fi

        local tmpdir
        tmpdir=$(mktemp -d)
        # Run block test in a temp directory (not a git repo) so even if the
        # guard fails, git reset --hard is harmless ("not a git repository").
        if sudo -u "$SUDO_USER" bash -c "cd '$tmpdir' && git reset --hard"; then
            log_error "Guard did not block git reset --hard"
            errors=1
        else
            log_info "Guard correctly blocked git reset --hard"
        fi
        rm -rf "$tmpdir"
    else
        log_warn "Running as root without sudo — skipping functional guard tests"
        log_warn "Guard blocks are verified on first non-root git invocation"
    fi

    if [[ $errors -eq 0 ]]; then
        echo ""
        log_info "Git guard installation complete."
        log_info "  /usr/bin/git          (4555 SUID root)"
        log_info "  /usr/bin/git.original (0755 root:root, immutable)"
        log_info "  dpkg-divert configured"
        log_info "  apt hook registered"
        log_info "  audit log: /var/log/ami-git-guard/"
        echo ""
        log_info "To verify: sudo make pre-req --check-git-guard"
    else
        log_error "Installation verification failed — rolling back"
        rollback_guard
        return 1
    fi

    return 0
}

check_guard() {
    if preflight_check; then
        log_info "Git guard status: INSTALLED"
        if [[ -f /usr/bin/git ]]; then
            log_info "  /usr/bin/git: $(stat -c '%a %U:%G' /usr/bin/git)"
        else
            log_warn "  /usr/bin/git: MISSING"
        fi
        if [[ -f /usr/bin/git.original ]]; then
            log_info "  /usr/bin/git.original: $(stat -c '%a %U:%G' /usr/bin/git.original)"
        else
            log_warn "  /usr/bin/git.original: MISSING"
        fi
        if divert_is_active; then
            log_info "  dpkg-divert: ACTIVE"
        else
            log_warn "  dpkg-divert: MISSING"
        fi
        if [[ -f /etc/apt/apt.conf.d/99git-guard ]]; then
            log_info "  apt hook: INSTALLED"
        else
            log_warn "  apt hook: MISSING"
        fi
        if [[ -f /usr/bin/git ]] && command -v lsattr >/dev/null; then
            if lsattr /usr/bin/git | grep -q '^....i'; then
                log_info "  immutable: YES"
            else
                log_warn "  immutable: NO"
            fi
        else
            log_warn "  immutable: SKIPPED (lsattr unavailable)"
        fi
    else
        log_info "Git guard status: NOT INSTALLED"
        log_info "To install: sudo make pre-req"
    fi
}

case "$MODE" in
    uninstall) uninstall_guard ;;
    check) check_guard ;;
    reinstall|install) install_guard ;;
    *) log_error "Unknown mode: $MODE"; exit 1 ;;
esac
