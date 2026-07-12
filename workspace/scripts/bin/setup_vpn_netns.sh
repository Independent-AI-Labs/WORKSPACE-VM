#!/usr/bin/env bash
set -euo pipefail

# Ensure a Linux network namespace exists with OpenVPN running inside it.

NETNS=""
CONFIG=""
AUTH=""
BINARY=""

usage() {
    echo "Usage: $0 --netns NAME --config PATH [--auth PATH] [--binary PATH]" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --netns)
            NETNS="${2:-}"
            shift 2
            ;;
        --config)
            CONFIG="${2:-}"
            shift 2
            ;;
        --auth)
            AUTH="${2:-}"
            shift 2
            ;;
        --binary)
            BINARY="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            ;;
    esac
done

if [[ -z "$NETNS" || -z "$CONFIG" ]]; then
    usage
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "[ERROR] VPN config not found: $CONFIG" >&2
    exit 1
fi

if [[ -z "$BINARY" ]]; then
    echo "[ERROR] --binary is required" >&2
    exit 1
fi

if [[ ! -x "$BINARY" ]]; then
    echo "[ERROR] openvpn binary not executable: $BINARY" >&2
    exit 1
fi

if ! command -v sudo &>/dev/null; then
    echo "[ERROR] sudo is required for ip netns operations" >&2
    exit 1
fi

_netns_add_rc=0
sudo ip netns add "$NETNS" 2>&1 || _netns_add_rc=$?
if [ "${_netns_add_rc}" -ne 0 ]; then
    if ! sudo ip netns list | grep -qE "^${NETNS}[[:space:]]"; then
        echo "[ERROR] failed to create or find netns: $NETNS" >&2
        exit 1
    fi
fi

sudo ip netns exec "$NETNS" ip link set lo up

AUTH_ARGS=()
if [[ -n "$AUTH" ]]; then
    if [[ ! -f "$AUTH" ]]; then
        echo "[ERROR] auth file not found: $AUTH" >&2
        exit 1
    fi
    AUTH_ARGS=(--auth-user-pass "$AUTH")
fi

sudo ip netns exec "$NETNS" "$BINARY" --config "$CONFIG" "${AUTH_ARGS[@]}" --daemon

_tun_rc=0
sudo ip netns exec "$NETNS" ip addr show tun0 >/dev/null 2>&1 || _tun_rc=$?
if [ "${_tun_rc}" -ne 0 ]; then
    echo "[ERROR] tun0 not up inside netns $NETNS" >&2
    exit 1
fi

echo "[INFO] OpenVPN running in netns $NETNS"