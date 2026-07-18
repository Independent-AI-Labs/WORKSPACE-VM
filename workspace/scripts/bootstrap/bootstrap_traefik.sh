#!/usr/bin/env bash
set -euo pipefail
OP="bootstrap_traefik"
TRAEFIK_VERSION="3.7.4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMI_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BOOT_DIR="${BOOT_LINUX_DIR:-${AMI_ROOT}/.boot-linux}"
BIN_DIR="${BOOT_DIR}/bin"

TARGET="${BIN_DIR}/traefik"

if [[ -x "$TARGET" ]]; then
    echo "[${OP}] traefik already installed at ${TARGET}"
    exit 0
fi

if ! command -v curl ; then
    echo "[${OP}] curl is required but not available"
    exit 1
fi

ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  TRAEFIK_ARCH="amd64" ;;
    aarch64) TRAEFIK_ARCH="arm64" ;;
    *)       echo "[${OP}] unsupported architecture: ${ARCH}"; exit 1 ;;
esac

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

TARBALL="traefik_v${TRAEFIK_VERSION}_linux_${TRAEFIK_ARCH}.tar.gz"
URL="https://github.com/traefik/traefik/releases/download/v${TRAEFIK_VERSION}/${TARBALL}"

echo "[${OP}] Downloading traefik v${TRAEFIK_VERSION} (${TRAEFIK_ARCH})..."
if ! HTTP_CODE=$(curl -sSLo "${TMPDIR}/${TARBALL}" -w "%{http_code}" "$URL"); then
    echo "[${OP}] curl failed - check network connectivity"
    exit 1
fi

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "[${OP}] download failed (HTTP ${HTTP_CODE}) - check network or try later"
    exit 1
fi

if [[ ! -s "${TMPDIR}/${TARBALL}" ]]; then
    echo "[${OP}] downloaded file is empty"
    exit 1
fi

tar -xzf "${TMPDIR}/${TARBALL}" -C "$TMPDIR" traefik
install -m 0755 "${TMPDIR}/traefik" "$TARGET"
echo "[${OP}] traefik v${TRAEFIK_VERSION} installed → ${TARGET}"
