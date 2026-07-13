#!/usr/bin/env bash
# Intel GPU provisioning for llama.cpp / llamafile workloads.
#
# Modes (mutually exclusive flags):
#   --monitoring-only  xpu-smi + clinfo (minimal apt; Intel PPA if needed)
#   --drivers          full compute + media stack + render/video groups (default)
#   --oneapi           --drivers plus Intel oneAPI SYCL/MKL toolchains
#
# Usage:
#   sudo bash scripts/setup/install-intel-gpu.sh
#   sudo bash scripts/setup/install-intel-gpu.sh --monitoring-only
#   sudo bash scripts/setup/install-intel-gpu.sh --oneapi
set -euo pipefail

MODE="drivers"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --monitoring-only)
            MODE="monitoring"
            ;;
        --drivers)
            MODE="drivers"
            ;;
        --oneapi)
            MODE="oneapi"
            ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0
            ;;
        *)
            printf 'error: unknown argument: %s\n' "$1" >&2
            exit 1
            ;;
    esac
    shift
done

if [ "$(id -u)" -ne 0 ]; then
    printf 'error: run as root (sudo bash %s)\n' "$0" >&2
    exit 1
fi

TARGET_USER="${SUDO_USER:-${USER}}"
if [ "$TARGET_USER" = "root" ]; then
    TARGET_USER="${USER:-agent}"
fi

print_verify_hints() {
    cat <<'EOF'
=========================================================================
 SETUP COMPLETE!
=========================================================================
To apply render/video group membership in the current shell:
  newgrp render

Verify Intel GPU stack:
  clinfo | grep "Device Name"
  vainfo | grep -i intel
  xpu-smi stats
=========================================================================
EOF
}

ensure_intel_graphics_ppa() {
    echo "=== Adding Intel Graphics PPA (Ubuntu 24.04) ==="
    rm -f /etc/apt/sources.list.d/intel-gpu-noble.list
    apt-get update
    apt-get install -y software-properties-common
    add-apt-repository -y ppa:kobuk-team/intel-graphics
    apt-get update
}

install_monitoring_packages() {
    echo "=== Installing Intel GPU monitoring packages ==="
    apt-get install -y clinfo xpu-smi
}

install_driver_packages() {
    echo "=== Installing Intel compute and OpenCL packages ==="
    apt-get install -y \
        libze-intel-gpu1 \
        libze1 \
        intel-metrics-discovery \
        intel-metrics-library \
        intel-opencl-icd \
        clinfo \
        intel-gsc \
        xpu-smi

    echo "=== Installing Intel media accelerator packages ==="
    apt-get install -y \
        intel-media-va-driver-non-free \
        libmfx-gen1 \
        libvpl2 \
        va-driver-all \
        vainfo
}

configure_user_groups() {
    echo "=== Configuring render/video group membership ==="
    gpasswd -a "${TARGET_USER}" render
    gpasswd -a "${TARGET_USER}" video
}

install_oneapi_packages() {
    echo "=== Installing Intel oneAPI SYCL/MKL packages ==="
    rm -f /etc/apt/sources.list.d/oneAPI.list
    wget -qO - https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
        | gpg --yes --dearmor \
        | tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
        | tee /etc/apt/sources.list.d/oneAPI.list
    apt-get update
    apt-get install -y \
        intel-oneapi-compiler-dpcpp-cpp \
        intel-oneapi-mkl \
        intel-oneapi-mkl-devel
    apt-get install -y libssl-dev
}

case "$MODE" in
    monitoring)
        echo "=== Intel GPU monitoring-only install ==="
        if ! command -v xpu-smi >/dev/null 2>&1; then
            ensure_intel_graphics_ppa
        fi
        install_monitoring_packages
        ;;
    drivers)
        echo "=== Intel GPU driver stack install ==="
        ensure_intel_graphics_ppa
        install_driver_packages
        configure_user_groups
        ;;
    oneapi)
        echo "=== Intel GPU full stack + oneAPI install ==="
        rm -f /etc/apt/sources.list.d/intel-gpu-noble.list
        rm -f /etc/apt/sources.list.d/oneAPI.list
        wget -qO - https://repositories.intel.com/gpu/intel-graphics.key \
            | gpg --yes --dearmor \
            | tee /usr/share/keyrings/intel-graphics.gpg > /dev/null
        ensure_intel_graphics_ppa
        install_driver_packages
        install_oneapi_packages
        configure_user_groups
        ;;
esac

print_verify_hints