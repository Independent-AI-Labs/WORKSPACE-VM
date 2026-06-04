#!/usr/bin/env bash

# Script to bootstrap Rust and Cargo
# Installs Rust toolchain into .boot-linux/rust using rustup

set -euo pipefail

# Logging functions
log_info() { echo "$1" >&2; }
log_error() { echo "ERROR: $1" >&2; }
log_success() { echo "✓ $1" >&2; }

# Calculate paths - script is in ami/scripts/bootstrap/, project root is 3 levels up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Use BOOT_LINUX_DIR env var if set, otherwise default
BOOT_DIR="${BOOT_LINUX_DIR:-${PROJECT_ROOT}/.boot-linux}"
RUST_HOME="$BOOT_DIR/rust"

# Ensure .boot-linux exists
if [ ! -d "$BOOT_DIR" ]; then
    log_error ".boot-linux directory not found. Please run install first."
    exit 1
fi

_create_symlinks() {
    local toolchain_name bin_dir toolchain_dir toolchain_bin toolchain_llvm_bin
    toolchain_name=$("$RUST_HOME/bin/rustup" show active-toolchain 2>&1 | awk 'NR==1{print $1}')
    if [[ -z "$toolchain_name" ]]; then
        toolchain_name="stable-x86_64-unknown-linux-gnu"
    fi
    toolchain_dir="rust/toolchains/${toolchain_name}"
    toolchain_bin="${toolchain_dir}/bin"
    toolchain_llvm_bin="${toolchain_dir}/lib/rustlib/x86_64-unknown-linux-gnu/bin"

    bin_dir="${BOOT_DIR}/bin"
    mkdir -p "${bin_dir}"

    ln -sf "../rust/bin/rustup" "${bin_dir}/rustup"

    for bin in cargo rustc rustfmt cargo-clippy cargo-fmt clippy-driver rustdoc; do
        if [ -x "${BOOT_DIR}/${toolchain_bin}/${bin}" ]; then
            ln -sf "../${toolchain_bin}/${bin}" "${bin_dir}/${bin}"
        fi
    done

    if [ -d "${BOOT_DIR}/${toolchain_llvm_bin}" ]; then
        for bin in "${BOOT_DIR}/${toolchain_llvm_bin}"/*; do
            [ -x "$bin" ] || continue
            [ -d "$bin" ] && continue
            bin_name="$(basename "$bin")"
            ln -sf "../${toolchain_llvm_bin}/${bin_name}" "${bin_dir}/${bin_name}"
        done
        log_success "LLVM tool symlinks created (llvm-profdata, llvm-cov, etc.)"
    else
        log_info "Warning: LLVM tools directory not found at ${toolchain_llvm_bin}"
    fi

    log_success "Rust symlinks created in ${bin_dir}"
}

_setup_cargo_config() {
    cat > "$RUST_HOME/config.toml" << 'TOML'
[target.x86_64-unknown-linux-gnu]
linker = "gcc-glibc"
TOML
    log_success "Global cargo config created (glibc gcc linker for x86_64-unknown-linux-gnu)"
}

_install_components() {
    log_info "Installing additional Rust components..."
    "$RUST_HOME/bin/rustup" component add llvm-tools-preview rust-src
    log_success "Components installed: llvm-tools-preview, rust-src"
}

# Check if already installed AND working (toolchain must be configured)
if [ -x "$RUST_HOME/bin/rustc" ] && [ -x "$RUST_HOME/bin/cargo" ]; then
    export RUSTUP_HOME="$RUST_HOME"
    export CARGO_HOME="$RUST_HOME"
    if EXISTING_VER=$("$RUST_HOME/bin/rustc" --version 2>/dev/null); then
        log_info "Rust is already installed: $EXISTING_VER"
        _create_symlinks
        exit 0
    else
        log_info "Rust binaries exist but toolchain is broken, reinstalling..."
        rm -rf "$RUST_HOME"
    fi
fi

log_info "Bootstrapping Rust toolchain..."

# Set rustup/cargo home to our isolated directory
export RUSTUP_HOME="$RUST_HOME"
export CARGO_HOME="$RUST_HOME"

# Create directory
mkdir -p "$RUST_HOME"

# Download and run rustup-init
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

cd "$TEMP_DIR"

log_info "Downloading rustup-init..."
if command -v curl >/dev/null 2>&1; then
    curl -sSf https://sh.rustup.rs -o rustup-init.sh
elif command -v wget >/dev/null 2>&1; then
    wget -q -O rustup-init.sh https://sh.rustup.rs
else
    log_error "Neither curl nor wget found."
    exit 1
fi

# Check if a C linker is available (required by Rust toolchain)
if ! command -v cc &>/dev/null && ! command -v gcc &>/dev/null && ! command -v clang &>/dev/null; then
    log_error "No C compiler (cc/gcc/clang) found — required by Rust toolchain."
    log_error "Run: sudo make init"
    exit 1
fi

log_info "Installing Rust (this may take a moment)..."
# Run rustup-init non-interactively
# -y: don't prompt
# --no-modify-path: don't touch shell profiles
# --default-toolchain stable: install stable Rust
# Output suppressed — rustup prints verbose component-by-component progress and
# a patronising "Rust is installed now. Great!" message. Our own log_success
# on the next line is the single source of truth.
sh rustup-init.sh -y --no-modify-path --default-toolchain stable >/dev/null 2>&1

cd - >/dev/null

# Verify installation
if [ ! -x "$RUST_HOME/bin/rustc" ]; then
    log_error "rustc not found after installation"
    exit 1
fi

if [ ! -x "$RUST_HOME/bin/cargo" ]; then
    log_error "cargo not found after installation"
    exit 1
fi

log_success "Rust installed to $RUST_HOME"
"$RUST_HOME/bin/rustc" --version
"$RUST_HOME/bin/cargo" --version

if [ ! -x "$BOOT_DIR/bin/gcc-glibc" ]; then
    log_info "Bootstrapping glibc GCC for Rust linker..."
    bash "$SCRIPT_DIR/bootstrap_gcc_glibc.sh"
fi

_create_symlinks
_setup_cargo_config
_install_components
