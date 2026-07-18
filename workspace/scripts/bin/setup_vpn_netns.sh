ip addr show tun0 || _tun_rc=$?#!/usr/bin/env bash
ip addr show tun0 || _tun_rc=$?set -euo pipefail
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?# Ensure a Linux network namespace exists with OpenVPN running inside it.
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?NETNS=""
ip addr show tun0 || _tun_rc=$?CONFIG=""
ip addr show tun0 || _tun_rc=$?AUTH=""
ip addr show tun0 || _tun_rc=$?BINARY=""
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?usage() {
ip addr show tun0 || _tun_rc=$?    echo "Usage: $0 --netns NAME --config PATH [--auth PATH] [--binary PATH]" >&2
ip addr show tun0 || _tun_rc=$?    exit 1
ip addr show tun0 || _tun_rc=$?}
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?while [[ $# -gt 0 ]]; do
ip addr show tun0 || _tun_rc=$?    case "$1" in
ip addr show tun0 || _tun_rc=$?        --netns)
ip addr show tun0 || _tun_rc=$?            NETNS="${2:-}"
ip addr show tun0 || _tun_rc=$?            shift 2
ip addr show tun0 || _tun_rc=$?            ;;
ip addr show tun0 || _tun_rc=$?        --config)
ip addr show tun0 || _tun_rc=$?            CONFIG="${2:-}"
ip addr show tun0 || _tun_rc=$?            shift 2
ip addr show tun0 || _tun_rc=$?            ;;
ip addr show tun0 || _tun_rc=$?        --auth)
ip addr show tun0 || _tun_rc=$?            AUTH="${2:-}"
ip addr show tun0 || _tun_rc=$?            shift 2
ip addr show tun0 || _tun_rc=$?            ;;
ip addr show tun0 || _tun_rc=$?        --binary)
ip addr show tun0 || _tun_rc=$?            BINARY="${2:-}"
ip addr show tun0 || _tun_rc=$?            shift 2
ip addr show tun0 || _tun_rc=$?            ;;
ip addr show tun0 || _tun_rc=$?        -h|--help)
ip addr show tun0 || _tun_rc=$?            usage
ip addr show tun0 || _tun_rc=$?            ;;
ip addr show tun0 || _tun_rc=$?        *)
ip addr show tun0 || _tun_rc=$?            echo "Unknown argument: $1" >&2
ip addr show tun0 || _tun_rc=$?            usage
ip addr show tun0 || _tun_rc=$?            ;;
ip addr show tun0 || _tun_rc=$?    esac
ip addr show tun0 || _tun_rc=$?done
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?if [[ -z "$NETNS" || -z "$CONFIG" ]]; then
ip addr show tun0 || _tun_rc=$?    usage
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?if [[ ! -f "$CONFIG" ]]; then
ip addr show tun0 || _tun_rc=$?    echo "[ERROR] VPN config not found: $CONFIG" >&2
ip addr show tun0 || _tun_rc=$?    exit 1
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?if [[ -z "$BINARY" ]]; then
ip addr show tun0 || _tun_rc=$?    echo "[ERROR] --binary is required" >&2
ip addr show tun0 || _tun_rc=$?    exit 1
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?if [[ ! -x "$BINARY" ]]; then
ip addr show tun0 || _tun_rc=$?    echo "[ERROR] openvpn binary not executable: $BINARY" >&2
ip addr show tun0 || _tun_rc=$?    exit 1
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?if ! command -v sudo ; then
ip addr show tun0 || _tun_rc=$?    echo "[ERROR] sudo is required for ip netns operations" >&2
ip addr show tun0 || _tun_rc=$?    exit 1
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?_netns_add_rc=0
ip addr show tun0 || _tun_rc=$?sudo ip netns add "$NETNS" 2>&1 || _netns_add_rc=$?
ip addr show tun0 || _tun_rc=$?if [ "${_netns_add_rc}" -ne 0 ]; then
ip addr show tun0 || _tun_rc=$?    if ! sudo ip netns list | grep -qE "^${NETNS}[[:space:]]"; then
ip addr show tun0 || _tun_rc=$?        echo "[ERROR] failed to create or find netns: $NETNS" >&2
ip addr show tun0 || _tun_rc=$?        exit 1
ip addr show tun0 || _tun_rc=$?    fi
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?sudo ip netns exec "$NETNS" ip link set lo up
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?AUTH_ARGS=()
ip addr show tun0 || _tun_rc=$?if [[ -n "$AUTH" ]]; then
ip addr show tun0 || _tun_rc=$?    if [[ ! -f "$AUTH" ]]; then
ip addr show tun0 || _tun_rc=$?        echo "[ERROR] auth file not found: $AUTH" >&2
ip addr show tun0 || _tun_rc=$?        exit 1
ip addr show tun0 || _tun_rc=$?    fi
ip addr show tun0 || _tun_rc=$?    AUTH_ARGS=(--auth-user-pass "$AUTH")
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?sudo ip netns exec "$NETNS" "$BINARY" --config "$CONFIG" "${AUTH_ARGS[@]}" --daemon
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?_tun_rc=0
sudo ip netns exec "$NETNS" ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?if [ "${_tun_rc}" -ne 0 ]; then
ip addr show tun0 || _tun_rc=$?    echo "[ERROR] tun0 not up inside netns $NETNS" >&2
ip addr show tun0 || _tun_rc=$?    exit 1
ip addr show tun0 || _tun_rc=$?fi
ip addr show tun0 || _tun_rc=$?
ip addr show tun0 || _tun_rc=$?echo "[INFO] OpenVPN running in netns $NETNS"