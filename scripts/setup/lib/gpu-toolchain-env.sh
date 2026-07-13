#!/usr/bin/env bash
# Shared glibc toolchain PATH for GPU builds (llama.cpp Vulkan, llamafile cosmo_dlopen).
#
# The workspace prepends ~/.boot-linux musl gcc; GPU DSO builds need system glibc cc/g++.
#
#   source "$(dirname "$0")/lib/gpu-toolchain-env.sh"
#   gpu_toolchain_env_init
set -euo pipefail

gpu_toolchain_env_init() {
    local boot_prefix="${HOME}/.boot-linux/bin"
    if [ -n "${PATH:-}" ]; then
        PATH="/usr/bin:${PATH}"
        PATH="${PATH//:${boot_prefix}/}"
        PATH="${PATH//${boot_prefix}:/}"
        export PATH
    else
        export PATH="/usr/bin"
    fi
    export CC="${CC:-/usr/bin/gcc}"
    export CXX="${CXX:-/usr/bin/g++}"
}