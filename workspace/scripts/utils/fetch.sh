#!/bin/bash
# Shared download helper for bootstrap scripts.
#
# Downloads a URL to a destination with curl or wget, failing loudly when
# neither is available or the transfer fails. Keeping this in one scanned
# place stops every bootstrap script from re-implementing the same
# download block.

fetch_file() {
    local url="$1"
    local dest="$2"
    local curl_bin
    local wget_bin

    curl_bin="$(command -v curl)" || curl_bin=""
    wget_bin="$(command -v wget)" || wget_bin=""

    if [[ -n "$curl_bin" ]]; then
        "$curl_bin" -fL --retry 3 -o "$dest" "$url"
    elif [[ -n "$wget_bin" ]]; then
        "$wget_bin" -q -O "$dest" "$url"
    else
        echo "fetch_file: neither curl nor wget found" >&2
        return 1
    fi
}
