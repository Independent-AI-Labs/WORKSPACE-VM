#!/bin/bash
set -euo pipefail

oc_wrapper_config_dir() {
    if [[ -n "${OPENCODE_CONFIG_DIR:-}" ]]; then
        printf '%s\n' "$OPENCODE_CONFIG_DIR"
    else
        printf '%s/opencode\n' "${XDG_CONFIG_HOME:-${HOME}/.config}"
    fi
}

oc_wrapper_welcome() {
    local welcome_file

    welcome_file="$(oc_wrapper_config_dir)/workspace-environment.md"
    if [[ -s "$welcome_file" ]]; then
        printf '%s\n' "$(< "$welcome_file")"
    else
        printf '%s\n' 'WORKSPACE-VM workspace'
    fi
}

oc_wrapper_prepare() {
    local workspace_root="$1"
    local welcome="$2"
    local oc_dir
    local oc_src="${workspace_root}/workspace/config/opencode"

    oc_dir="$(oc_wrapper_config_dir)"
    mkdir -p "$oc_dir"
    printf '%b\n' "$welcome" > "${oc_dir}/workspace-environment.md"
    if [[ ! -f "${oc_dir}/opencode.jsonc" ]]; then
        cp "${oc_src}/opencode.jsonc" "${oc_dir}/opencode.jsonc"
    fi
    if [[ ! -f "${oc_dir}/system-instruction.md" ]]; then
        cp "${oc_src}/system-instruction.template.md" "${oc_dir}/system-instruction.md"
    fi
    export OPENCODE_CONFIG_DIR="$oc_dir"
    export OPENCODE_CONFIG_CONTENT='{"subagent_depth":0,"agent":{"explore":{"disable":true},"general":{"disable":true}},"permission":{"task":"deny"}}'
    export OPENCODE_ENABLE_EXA=1
    export OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS=600000
}

oc_wrapper_shard_db() {
    if [[ -n "${OPENCODE_DB:-}" ]]; then
        return 0
    fi
    local root hash data_dir map
    if root=$(git rev-parse --show-toplevel 2>&1); then
        hash=$(printf '%s' "$root" | sha256sum | cut -c1-16)
        export OPENCODE_DB="shard-${hash}.db"
        data_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/opencode"
        mkdir -p "$data_dir"
        map="${data_dir}/shards.tsv"
        touch "$map"
        if ! grep -qF "$hash" "$map"; then
            printf '%s\t%s\n' "$hash" "$root" >> "$map"
        fi
        printf '[oc] db shard: %s (%s)\n' "$OPENCODE_DB" "$root" >&2
    fi
}

oc_wrapper_dispatch() {
    local opencode="$1"
    local original_pwd="$2"
    local db=""
    local has_db=0
    local mono=0
    local direct=0
    local -a args=()
    shift 2

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --mono)
                mono=1
                shift
                ;;
            --db)
                if [[ $# -lt 2 ]]; then
                    echo "oc: --db requires a name" >&2
                    return 2
                fi
                db="$2"
                has_db=1
                shift 2
                ;;
            --db=*)
                db="${1#--db=}"
                has_db=1
                shift
                ;;
            --)
                direct=1
                shift
                args=("$@")
                break
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done

    if [[ $mono -eq 1 && $has_db -eq 1 ]]; then
        echo "oc: --mono and --db are mutually exclusive" >&2
        return 2
    fi
    if [[ $mono -eq 1 ]]; then
        unset OPENCODE_DB
        echo "[oc] db: monolith (opencode default naming)" >&2
    elif [[ $has_db -eq 1 ]]; then
        export OPENCODE_DB="$db"
    else
        oc_wrapper_shard_db
    fi
    if [[ $direct -eq 1 ]]; then
        exec "$opencode" "${args[@]}"
    fi
    if [[ ${#args[@]} -eq 0 ]]; then
        exec "$opencode"
    fi
    if [[ "${args[0]}" == -* ]]; then
        exec "$opencode" "${args[@]}"
    fi
    exec "$opencode" run --dir "$original_pwd" "${args[@]}"
}
