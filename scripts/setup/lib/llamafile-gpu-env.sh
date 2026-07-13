#!/usr/bin/env bash
# Shared GPU runtime/build environment for llamafile Vulkan backends.
#
# llamafile loads GPU DSOs via cosmo_dlopen(), which compiles ~/.cosmo/dlopen-helper
# using whatever `cc` is first on PATH. The workspace prepends .boot-linux musl gcc;
# a musl-linked helper cannot run on glibc hosts and every cosmo_dlopen() fails with:
#   "dlopen() isn't supported on this platform"
#
# Source this file from build, test, and server wrapper scripts:
#   source "$(dirname "$0")/lib/llamafile-gpu-env.sh"
#   llamafile_gpu_env_init
#   ensure_cosmo_dlopen_helper
set -euo pipefail

# shellcheck source=gpu-toolchain-env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gpu-toolchain-env.sh" || exit 1

llamafile_gpu_env_init() {
    gpu_toolchain_env_init
}

ensure_cosmo_dlopen_helper() {
    llamafile_gpu_env_init

    local cosmo_dir="${HOME}/.cosmo"
    local helper_src="${cosmo_dir}/dlopen-helper.c"
    local helper_bin="${cosmo_dir}/dlopen-helper"

    if [ ! -x "$CC" ]; then
        printf 'error: system C compiler not found at %s\n' "$CC" >&2
        printf 'hint: sudo apt-get install -y gcc\n' >&2
        return 1
    fi

    if [ ! -f "$helper_src" ]; then
        printf 'error: %s not found\n' "$helper_src" >&2
        printf 'hint: run llamafile once with --gpu vulkan so cosmo creates the source,\n' >&2
        printf '      or delete ~/.cosmo/ and retry after llamafile_gpu_env_init.\n' >&2
        return 1
    fi

    local rebuild=0
    if [ ! -x "$helper_bin" ]; then
        rebuild=1
    elif file -b "$helper_bin" | grep -q 'ld-musl'; then
        rebuild=1
    fi

    if [ "$rebuild" -eq 1 ]; then
        mkdir -p "$cosmo_dir"
        printf '=== Rebuilding %s with %s ===\n' "$helper_bin" "$CC"
        "$CC" -pie -fPIC "$helper_src" -o "$helper_bin" -Wl,-z,execstack -ldl
    fi

    if file -b "$helper_bin" | grep -q 'ld-musl'; then
        printf 'error: dlopen-helper is still musl-linked after rebuild\n' >&2
        return 1
    fi
}