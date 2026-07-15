#!/usr/bin/env bash
set -euo pipefail

# Bootstrap QEMU into the platform boot directory (GPL-2.0 binaries, subprocess-only).
# See docs/SPEC-VM-HYPERVISOR.md §10.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

_boot_platform="$(uname -s | tr 'A-Z' 'a-z')"
case "$_boot_platform" in darwin) _boot_default=".boot-macos" ;; *) _boot_default=".boot-linux" ;; esac
BOOT_DIR="${BOOT_DIR:-${BOOT_LINUX_DIR:-${PROJECT_ROOT}/${_boot_default}}}"
BIN_DIR="${BOOT_DIR}/bin"
SHARE_DIR="${BOOT_DIR}/share/qemu"
FIRMWARE_DIR="${SHARE_DIR}/firmware"
mkdir -p "${BIN_DIR}" "${FIRMWARE_DIR}"

PINS_FILE="${PROJECT_ROOT}/res/qemu-pins.yaml"
LICENSE_DST="${SHARE_DIR}/LICENSE"
NOTICE_DST="${SHARE_DIR}/NOTICE"

log() { echo "[bootstrap-qemu] $*"; }
warn() { echo "[bootstrap-qemu] WARNING: $*" >&2; }

install_linux() {
    if ! command -v apt-get &>/dev/null; then
        echo "bootstrap-qemu: apt-get required on Linux" >&2
        exit 1
    fi
    sudo apt-get update -qq
    sudo apt-get install -y qemu-system-arm qemu-system-x86 qemu-utils qemu-efi-aarch64 genisoimage cloud-image-utils

    for bin in qemu-system-aarch64 qemu-system-x86_64 qemu-img; do
        src="$(command -v "$bin")"
        ln -sf "$src" "${BIN_DIR}/${bin}"
    done

    for tool in genisoimage mkisofs cloud-localds; do
        if src="$(command -v "$tool")"; then
            ln -sf "$src" "${BIN_DIR}/${tool}"
        fi
    done

    if [[ -f /usr/share/qemu-efi-aarch64/QEMU_EFI.fd ]]; then
        ln -sf /usr/share/qemu-efi-aarch64/QEMU_EFI.fd "${FIRMWARE_DIR}/QEMU_EFI.fd"
    fi
}

install_darwin() {
    if ! command -v brew &>/dev/null; then
        echo "bootstrap-qemu: Homebrew required on macOS" >&2
        exit 1
    fi
    brew install qemu

    prefix="$(brew --prefix qemu)"
    for bin in qemu-system-aarch64 qemu-system-x86_64 qemu-img; do
        src="${prefix}/bin/${bin}"
        if [[ -x "$src" ]]; then
            ln -sf "$src" "${BIN_DIR}/${bin}"
        fi
    done

    fw="${prefix}/share/qemu/edk2-aarch64-code.fd"
    if [[ -f "$fw" ]]; then
        ln -sf "$fw" "${FIRMWARE_DIR}/QEMU_EFI.fd"
    fi

    if ! command -v cloud-localds &>/dev/null; then
        _vendor_url="https://raw.githubusercontent.com/canonical/cloud-utils/master/bin/cloud-localds"
        if curl -fsSL "$_vendor_url" -o "${BIN_DIR}/cloud-localds"; then
            chmod +x "${BIN_DIR}/cloud-localds"
            log "vendored cloud-localds into ${BIN_DIR}"
        else
            warn "cloud-localds not found; install cloud-image-utils (Linux) or re-run bootstrap"
        fi
    fi

    if ! command -v genisoimage &>/dev/null && command -v mkisofs &>/dev/null; then
        ln -sf "$(command -v mkisofs)" "${BIN_DIR}/genisoimage"
        log "linked genisoimage -> mkisofs in ${BIN_DIR}"
    fi
}

write_notices() {
    if [[ -f /usr/share/common-licenses/GPL-2 ]]; then
        cp /usr/share/common-licenses/GPL-2 "${LICENSE_DST}"
    elif curl -fsSL "https://www.qemu.org/license-gpl-2/" -o "${LICENSE_DST}"; then
        :
    else
        warn "could not download GPL-2 license text"
    fi

    version="unknown"
    if [[ -x "${BIN_DIR}/qemu-system-aarch64" ]]; then
        version="$("${BIN_DIR}/qemu-system-aarch64" --version)"
        version="${version%%$'\n'*}"
    fi
    qemu_version="$(echo "$version" | sed -n 's/.*version \([0-9.]*\).*/\1/p')"
    source_url="https://download.qemu.org/qemu-${qemu_version}.tar.xz"
    if [[ -f "$PINS_FILE" ]]; then
        pinned=""
        if pinned="$(cd "${PROJECT_ROOT}" && uv run python -c "import yaml; d=yaml.safe_load(open('${PINS_FILE}')); print(d.get('qemu',{}).get('source_url',''))")"; then
            if [[ -n "$pinned" ]]; then
                source_url="$pinned"
            fi
        else
            warn "could not read qemu source_url from ${PINS_FILE}"
        fi
    fi

    cat >"${NOTICE_DST}" <<EOF
QEMU system emulator (GPL-2.0)
Installed: ${version}
Binaries: qemu-system-aarch64, qemu-system-x86_64, qemu-img
Source: ${source_url}
License: GNU General Public License v2.0 - see ${LICENSE_DST}
Integration: invoked as external process only; workspace code does not link libqemu.
EOF
}

case "$(uname -s)" in
    Darwin) install_darwin ;;
    Linux) install_linux ;;
    *)
        echo "bootstrap-qemu: unsupported OS" >&2
        exit 1
        ;;
esac

write_notices
log "QEMU installed under ${BIN_DIR}"
if [[ -x "${BIN_DIR}/qemu-system-aarch64" ]]; then
    "${BIN_DIR}/qemu-system-aarch64" --version
else
    warn "qemu-system-aarch64 not present (optional on x86 hosts)"
fi