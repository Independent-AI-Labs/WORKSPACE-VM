#!/usr/bin/env bash
# Bootstrap: Build and install SUID rust guard (git PoC)
# Called by: initial-setup.sh (after apt dependencies installed)
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
    log_info "Uninstalling rust guard..."
    if command -v chattr >/dev/null; then
        chattr -i /usr/bin/git 2>/dev/null || true  # silent-ok: chattr may be absent or file already mutable
        chattr -i /usr/bin/git.original 2>/dev/null || true  # silent-ok: same
    fi
    rm -f /usr/bin/git
    if divert_is_active; then
        dpkg-divert --rename --remove /usr/bin/git
        log_info "Removed dpkg-divert"
    fi
    if [[ -f /usr/bin/git.original ]]; then
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
    # Clean up all guard-related system paths (current + former ami-git-guard)
    rm -f /etc/apt/apt.conf.d/99rust-guard
    rm -f /etc/apt/apt.conf.d/99git-guard
    rm -rf /usr/lib/rust-guard
    rm -rf /usr/lib/ami-git-guard
    rm -rf /var/log/rust-guard
    rm -rf /var/log/ami-git-guard
    log_info "Git guard uninstalled — /usr/bin/git restored, system paths cleaned"
    git --version
}

rollback_guard() {
    log_warn "Installation failed — rolling back..."
    if command -v chattr >/dev/null; then
        chattr -i /usr/bin/git 2>/dev/null || true  # silent-ok: chattr may fail if attribute already absent or binary missing during rollback
        chattr -i /usr/bin/git.original 2>/dev/null || true  # silent-ok: chattr may fail if attribute already absent or original missing during rollback
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
        if [[ "$gmode" == "700" && "$gowner" == "root:root" ]]; then
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
    if [[ "$MODE" != "reinstall" ]]; then
        if preflight_check; then
            log_info "To reinstall: sudo make init"
            return 0
        fi
    fi

    echo ""
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD} Git Guard Installation (SUID-root, git PoC)${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════${NC}"
    echo ""
    echo "This will:"
    echo "  - Build the rust-guard Rust binary from source"
    echo "  - Relocate /usr/bin/git -> /usr/bin/git.original (0700 root-only)"
    echo "  - Install the guard as /usr/bin/git (4555 SUID root)"
    echo "  - Configure dpkg-divert to protect from apt overwrites"
    echo "  - Remove previous .boot-linux/bin/git wrapper"
    echo "  - Set immutable attributes on the guard binary"
    echo "  - Register apt post-invoke hook for change detection"
    echo ""
    echo "After installation, ONLY the SUID guard can invoke real git."
    echo "To uninstall: bash workspace/scripts/bootstrap/bootstrap_rust_guard.sh uninstall"
    echo ""

    if [[ -t 0 ]] && [[ "$MODE" == "install" ]]; then
        echo -ne "${CYAN}${BOLD}Proceed with rust guard installation? [y/N] ${NC}"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY]) ;;
            *) log_info "Git guard installation cancelled."; return 0 ;;
        esac
    fi

    # Phase 1: Build Rust binary
    log_info "Building rust-guard Rust binary..."
    local boot_rust="${PROJECT_ROOT}/.boot-linux/bin"
    local rust_home="${PROJECT_ROOT}/.boot-linux/rust"
    export PATH="$boot_rust:$PATH"
    export RUSTUP_HOME="$rust_home"
    export CARGO_HOME="$rust_home"

    if ! command -v cargo >/dev/null; then
        log_warn "cargo not on PATH — bootstrapping Rust..."
        bash "${PROJECT_ROOT}/workspace/scripts/bootstrap/bootstrap_rust.sh" || {
            log_error "Rust installation failed"
            return 1
        }
        if ! command -v cargo >/dev/null; then
            log_error "cargo still not found after bootstrap — check $boot_rust/"
            return 1
        fi
        log_info "Rust bootstrapped successfully"
    fi

    local guard_dir="${PROJECT_ROOT}/projects/RUST-GUARD"
    if [[ ! -f "$guard_dir/Cargo.toml" ]]; then
        log_info "RUST-GUARD project not found at $guard_dir — cloning from remote..."

        # Forward SSH_AUTH_SOCK from the original user into sudo if missing
        if [[ -z "${SSH_AUTH_SOCK:-}" ]] && [[ -n "${SUDO_USER:-}" ]]; then
            local user_ssh_sock
            user_ssh_sock=$(sudo -u "$SUDO_USER" printenv SSH_AUTH_SOCK 2>/dev/null || true)  # silent-ok: user may not have SSH agent running
            if [[ -n "$user_ssh_sock" && -S "$user_ssh_sock" ]]; then
                export SSH_AUTH_SOCK="$user_ssh_sock"
                log_info "Forwarded SSH agent socket from $SUDO_USER"
            fi
        fi

        local guard_remote
        guard_remote=$(grep -A3 'rust-guard:' "${PROJECT_ROOT}/workspace/config/workspace-clones.yaml" | grep 'remote:' | awk '{print $2}' | tr -d "'\"")
        if [[ -z "$guard_remote" ]]; then
            guard_remote="git@github.com:Independent-AI-Labs/RUST-GUARD.git"
        fi
        mkdir -p "$(dirname "$guard_dir")"
        if ! sudo -u "${SUDO_USER:-$USER}" git clone "$guard_remote" "$guard_dir"; then
            log_error "Failed to clone RUST-GUARD from $guard_remote"
            return 1
        fi
        chown -R root:root "$guard_dir" 2>/dev/null || true  # silent-ok: non-fatal if sudo user owns dir
        log_info "RUST-GUARD cloned from $guard_remote"
    fi

    cd "$guard_dir"
    local guard_bin=""
    local has_rustup=0
    if command -v rustup >/dev/null; then
        has_rustup=1
    fi
    if [[ "$has_rustup" -eq 1 ]]; then
        local installed_targets
        installed_targets=$(rustup target list --installed)
        if echo "$installed_targets" | grep -q musl; then
            log_info "Building statically linked binary (musl)..."
            cargo build --release --target x86_64-unknown-linux-musl
            guard_bin="target/x86_64-unknown-linux-musl/release/rust-guard"
        else
            log_info "Building dynamically linked binary (gnu)..."
            PATH="/usr/bin:/usr/sbin:/usr/local/bin:$PATH" CC=gcc cargo build --release
            guard_bin="target/release/rust-guard"
        fi
    else
        log_info "Building dynamically linked binary (gnu, no rustup)..."
        PATH="/usr/bin:/usr/sbin:/usr/local/bin:$PATH" CC=gcc cargo build --release
        guard_bin="target/release/rust-guard"
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

    # Phase 2: Detect bypass vectors
    for path in /snap/bin/git /usr/local/bin/git; do
        if [[ -x "$path" ]]; then
            log_warn "Alternative git found at $path — this bypasses the guard"
        fi
    done

    # Phase 3: Divert + relocate git
    # Source for git.original — use git.distrib when diverted (not in use by checks)
    local git_src=""
    if divert_is_active && [[ -x /usr/bin/git.distrib ]]; then
        git_src="/usr/bin/git.distrib"
    elif [[ -x /usr/bin/git ]]; then
        git_src="/usr/bin/git"
    else
        log_error "System git not found"
        return 1
    fi

    # Copy to git.original first (remove immutability if present from previous install)
    if [[ -f /usr/bin/git.original ]] && command -v chattr >/dev/null; then
        chattr -i /usr/bin/git.original
    fi
    cp "$git_src" /usr/bin/git.original
    chown root:root /usr/bin/git.original
    chmod 0700 /usr/bin/git.original

    local src_hash copy_hash
    src_hash=$(sha256sum "$git_src" | awk '{print $1}')
    copy_hash=$(sha256sum /usr/bin/git.original | awk '{print $1}')
    if [[ "$src_hash" != "$copy_hash" ]]; then
        log_error "Checksum mismatch — git.original does not match"
        rm -f /usr/bin/git.original
        return 1
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
    cat > /etc/apt/apt.conf.d/99rust-guard << 'EOF'
DPkg::Post-Invoke { "/usr/lib/rust-guard/apt-check.sh"; };
EOF
    mkdir -p /usr/lib/rust-guard
    cat > /usr/lib/rust-guard/apt-check.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
if dpkg -l git | grep -q '^ii' && [[ ! -f /usr/bin/git.original ]]; then
    echo '[WARN] Git package changed but rust guard not detected. Re-run: sudo make init' >&2
fi
EOF
    chmod 755 /usr/lib/rust-guard/apt-check.sh

    # Create audit log directory
    mkdir -p /var/log/rust-guard
    chmod 1777 /var/log/rust-guard

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
    if [[ "$real_mode" != "700" || "$real_owner" != "root:root" ]]; then
        log_error "git.original has wrong permissions: $real_mode $real_owner"
        errors=1
    fi

    if sudo -u "${SUDO_USER:-$USER}" git --version; then
        log_info "git --version: $(git --version)"
    else
        log_error "git --version failed"
        errors=1
    fi

    local tmpdir
    tmpdir=$(mktemp -d)
    chmod 755 "$tmpdir"
    # Run destructive test in a temp directory (not a git repo) so even if the
    # guard fails, git reset --hard is harmless ("not a git repository").
    if sudo -u "${SUDO_USER:-$USER}" bash -c "cd '$tmpdir' && git reset --hard"; then
        log_error "Guard did not block git reset --hard"
        errors=1
    else
        log_info "Guard correctly blocked git reset --hard"
    fi
    rm -rf "$tmpdir"

    if [[ $errors -eq 0 ]]; then
        echo ""
        log_info "Rust guard (git PoC) installation complete."
        log_info "  /usr/bin/git          (4555 SUID root)"
        log_info "  /usr/bin/git.original (0700 root:root, immutable)"
        log_info "  dpkg-divert configured"
        log_info "  apt hook registered"
        log_info "  audit log: /var/log/rust-guard/"
        echo ""
        log_info "To verify: bash workspace/scripts/bootstrap/bootstrap_rust_guard.sh check"
    else
        log_error "Installation verification failed — rolling back"
        rollback_guard
        return 1
    fi

    return 0
}

check_guard() {
    if preflight_check; then
        log_info "Rust guard status: INSTALLED"
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
        if [[ -f /etc/apt/apt.conf.d/99rust-guard ]]; then
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
        log_info "Rust guard status: NOT INSTALLED"
        log_info "To install: sudo make init"
    fi
}

case "$MODE" in
    uninstall) uninstall_guard ;;
    check) check_guard ;;
    reinstall|install) install_guard ;;
    *) log_error "Unknown mode: $MODE"; exit 1 ;;
esac
