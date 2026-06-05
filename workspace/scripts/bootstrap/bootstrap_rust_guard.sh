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

MODE="${1:-install}"  # install | uninstall | reinstall | check | build-only | install-only

divert_is_active() {
    dpkg-divert --list /usr/bin/git | grep -q 'git.distrib'
}

uninstall_guard() {
    log_info "Uninstalling rust guard..."
    if command -v chattr >/dev/null; then
        test -f /usr/bin/git       && chattr -i /usr/bin/git
        test -f /usr/bin/git.original && chattr -i /usr/bin/git.original
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
        test -f /usr/bin/git       && chattr -i /usr/bin/git
        test -f /usr/bin/git.original && chattr -i /usr/bin/git.original
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

build_guard_binary() {
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

        if [[ -z "${SSH_AUTH_SOCK:-}" ]] && [[ -n "${SUDO_USER:-}" ]]; then
            local user_ssh_sock
            user_ssh_sock=$(sudo -u "$SUDO_USER" printenv SSH_AUTH_SOCK)
            local _ssh_rc=$?
            if [[ $_ssh_rc -eq 0 && -n "$user_ssh_sock" && -S "$user_ssh_sock" ]]; then
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
        chown -R root:root "$guard_dir"
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

    GUARD_BIN="$guard_bin"
    return 0
}

install_guard_binary() {
    local guard_bin="${1:-$GUARD_BIN}"
    if [[ ! -f "$guard_bin" ]]; then
        log_error "Guard binary not found at $guard_bin"
        log_error "Run 'make install' first to build the binary, then: sudo make install-guard"
        return 1
    fi
    if ! file "$guard_bin" | grep -q ELF; then
        log_error "Guard binary is not a valid ELF: $guard_bin"
        return 1
    fi

    echo ""
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD} Git Guard — File Capability Installation${NC}"
    echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "The Git Guard is a capability-enabled binary that wraps /usr/bin/git."
    echo ""
    echo "WHAT IT DOES:"
    echo "  • Relocates real git → /usr/bin/git.original (0700, root-only)"
    echo "  • Installs guard binary → /usr/bin/git (0755, cap_dac_override+ep)"
    echo "  • Gives users rights to run git ONLY through the guard"
    echo "  • Blocks: git reset --hard, git checkout --hard, git rebase,"
    echo "            git commit --amend, git push --force, git reset,"
    echo "            git checkout (destructive file restoration)"
    echo "  • Allows: git status, git log, git diff, git add, git commit,"
    echo "            git pull --ff-only, git fetch, git stash"
    echo "  • dpkg-divert protects from apt overwrites"
    echo "  • Immutable attributes (chattr +i) prevent tampering"
    echo "  • Logs every git invocation to /var/log/rust-guard/"
    echo ""
    echo "WHY IT'S RECOMMENDED:"
    echo "  • CI agents, AI coding assistants, and automated tooling can"
    echo "    inadvertently (or adversarially) destroy your repo history."
    echo "  • The guard provides a PROOF OF CONCEPT that git operations"
    echo "    can be policed at the OS level — no configuration changes"
    echo "    in your CI pipeline, IDE, or git config are needed."
    echo "  • Every blocked command is logged with user, timestamp, and"
    echo "    the exact git invocation that was attempted."
    echo ""
    echo "To uninstall:"
    echo "  sudo bash workspace/scripts/bootstrap/bootstrap_rust_guard.sh uninstall"
    echo ""

    if [[ -t 0 ]]; then
        echo -ne "${CYAN}${BOLD}Proceed with git guard installation? [y/N] ${NC}"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY]) ;;
            *) log_info "Git guard installation cancelled."; return 0 ;;
        esac
    fi

    # Phase 1: Divert + relocate git
    local git_src=""
    if divert_is_active && [[ -x /usr/bin/git.distrib ]]; then
        git_src="/usr/bin/git.distrib"
    elif [[ -x /usr/bin/git ]]; then
        git_src="/usr/bin/git"
    else
        log_error "System git not found at /usr/bin/git"
        return 1
    fi

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

    if divert_is_active; then
        log_warn "dpkg-divert already in place — continuing"
    else
        dpkg-divert --local --divert /usr/bin/git.distrib --rename --add /usr/bin/git
    fi
    chmod 0700 /usr/bin/git.distrib
    chown root:root /usr/bin/git.distrib

    if ! command -v setcap >/dev/null; then
        log_error "setcap not found — install libcap2-bin (apt install libcap2-bin)"
        return 1
    fi

    # Phase 2: Install guard binary with file capabilities
    if command -v chattr >/dev/null && [[ -f /usr/bin/git ]]; then
        chattr -i /usr/bin/git
    fi
    cp "$guard_bin" /usr/bin/git
    chown root:root /usr/bin/git
    chmod 0755 /usr/bin/git
    setcap cap_dac_override+ep /usr/bin/git || {
        log_error "Failed to set file capabilities on /usr/bin/git"
        return 1
    }

    if command -v chattr >/dev/null; then
        chattr +i /usr/bin/git || log_warn "Could not set immutable on /usr/bin/git"
        chattr +i /usr/bin/git.original || log_warn "Could not set immutable on /usr/bin/git.original"
    else
        log_warn "chattr not available — skipping immutable attributes"
    fi

    # Phase 3: Restrict bypass vectors
    if [[ -f "$PROJECT_ROOT/.boot-linux/bin/git" ]]; then
        rm -f "$PROJECT_ROOT/.boot-linux/bin/git"
        log_info "Removed previous bash wrapper at .boot-linux/bin/git"
    fi
    hash -r

    for path in /snap/bin/git /usr/local/bin/git; do
        if [[ -x "$path" ]]; then
            chmod 000 "$path"
            log_info "Restricted $path (bypass vector)"
        fi
    done

    # Phase 4: Register apt post-invoke hook
    cat > /etc/apt/apt.conf.d/99rust-guard << 'EOF'
DPkg::Post-Invoke { "/usr/lib/rust-guard/apt-check.sh"; };
EOF
    mkdir -p /usr/lib/rust-guard
    cat > /usr/lib/rust-guard/apt-check.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
if dpkg -l git | grep -q '^ii' && [[ ! -f /usr/bin/git.original ]]; then
    echo '[WARN] Git package changed but rust guard not detected. Re-run: sudo make install-guard' >&2
fi
if [[ -f /usr/bin/git.distrib ]]; then
    chmod 0700 /usr/bin/git.distrib
    chown root:root /usr/bin/git.distrib
fi
EOF
    chmod 755 /usr/lib/rust-guard/apt-check.sh

    mkdir -p /var/log/rust-guard
    chmod 1777 /var/log/rust-guard

    # Phase 5: Verification
    echo ""
    log_info "Running post-installation verification..."
    local errors=0

    local guard_mode guard_owner
    guard_mode=$(stat -c '%a' /usr/bin/git)
    guard_owner=$(stat -c '%U:%G' /usr/bin/git)
    if [[ "$guard_mode" != "755" || "$guard_owner" != "root:root" ]]; then
        log_error "Guard binary has wrong permissions: $guard_mode $guard_owner"
        errors=1
    fi
    if ! getcap /usr/bin/git | grep -q cap_dac_override; then
        log_error "Guard binary missing cap_dac_override capability"
        errors=1
    fi

    local real_mode real_owner
    real_mode=$(stat -c '%a' /usr/bin/git.original)
    real_owner=$(stat -c '%U:%G' /usr/bin/git.original)
    if [[ "$real_mode" != "700" || "$real_owner" != "root:root" ]]; then
        log_error "git.original has wrong permissions: $real_mode $real_owner"
        errors=1
    fi

    if git --version; then
        log_info "git --version: $(git --version)"
    else
        log_error "git --version failed"
        errors=1
    fi

    local tmpdir
    tmpdir=$(mktemp -d)
    chmod 755 "$tmpdir"
    if bash -c "cd '$tmpdir' && git reset --hard"; then
        log_error "Guard did not block git reset --hard"
        errors=1
    else
        log_info "Guard correctly blocked git reset --hard"
    fi
    rm -rf "$tmpdir"

    if [[ $errors -eq 0 ]]; then
        echo ""
        log_info "Git guard installation complete."
        log_info "  /usr/bin/git          (0755 root:root, cap_dac_override+ep, immutable)"
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

install_guard() {
    if [[ "$MODE" != "reinstall" ]]; then
        if preflight_check; then
            log_info "Git guard is already installed."
            log_info "To reinstall: make install && sudo make install-guard"
            return 0
        fi
    fi

    build_guard_binary || return 1
    install_guard_binary "$GUARD_BIN" || return 1
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
    build-only) build_guard_binary ;;
    install-only)
        GUARD_BIN="${PROJECT_ROOT}/projects/RUST-GUARD/target/release/rust-guard"
        install_guard_binary "$GUARD_BIN"
        ;;
    reinstall|install) install_guard ;;
    *) log_error "Unknown mode: $MODE"; exit 1 ;;
esac
