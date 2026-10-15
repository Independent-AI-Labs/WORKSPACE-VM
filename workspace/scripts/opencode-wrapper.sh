#!/bin/bash
set -euo pipefail

_OC_WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Path of the OpenCode config file that holds provider/model blocks.
oc_wrapper_config_file() {
    local dir
    dir="$(oc_wrapper_config_dir)"
    if [[ -f "${dir}/opencode.jsonc" ]]; then
        printf '%s\n' "${dir}/opencode.jsonc"
    elif [[ -f "${dir}/opencode.json" ]]; then
        printf '%s\n' "${dir}/opencode.json"
    else
        printf '%s\n' "${dir}/opencode.jsonc"
    fi
}

# Resolve "<provider>/<model>" to "<providerID>\t<modelSlug>", matching the
# provider/model keys first and their configured names second. Prints an ERR
# line with a candidate list when the spec is unknown or ambiguous.
oc_wrapper_resolve_target() {
    local jq_bin="$1" spec="$2" cfg="$3"
    local provider_spec model_spec
    if [[ "$spec" != */* ]]; then
        echo "oc: --set-ctx expects <provider>/<model>, got '${spec}'" >&2
        return 2
    fi
    provider_spec="${spec%%/*}"
    model_spec="${spec#*/}"
    "$jq_bin" -r --arg ps "$provider_spec" --arg ms "$model_spec" '
        (.provider // {}) as $p
        | [ $p | to_entries[] | select(.key == $ps or .value.name == $ps) ] as $pm
        | if ($pm | length) == 0 then
            "ERR\tNo provider matches \($ps). Known providers: " + ([ $p | keys[] ] | join(", "))
          elif ($pm | length) > 1 then
            "ERR\tProvider \($ps) is ambiguous: " + ([ $pm[].key ] | join(", "))
          else
            $pm[0].key as $pid
            | [ ($pm[0].value.models // {}) | to_entries[] | select(.key == $ms or .value.name == $ms) ] as $mm
            | if ($mm | length) == 0 then
                "ERR\tNo model matches \($ms) in \($pid). Known models: " + ([ ($pm[0].value.models // {}) | keys[] ] | join(", "))
              elif ($mm | length) > 1 then
                "ERR\tModel \($ms) is ambiguous in \($pid): " + ([ $mm[].key ] | join(", "))
              else
                "OK\t\($pid)\t\($mm[0].key)"
              end
          end
    ' "$cfg"
}

# Write limit.context into the config file in place, keeping a .bak copy.
oc_wrapper_persist_ctx() {
    local jq_bin="$1" cfg="$2" provider_id="$3" model_slug="$4" size="$5"
    local tmp
    tmp="$(mktemp "${cfg}.XXXXXX")"
    if ! "$jq_bin" --arg p "$provider_id" --arg m "$model_slug" --argjson n "$size" \
        '.provider[$p].models[$m].limit.context = $n' "$cfg" > "$tmp"; then
        rm -f "$tmp"
        echo "oc: --set-ctx could not update ${cfg}" >&2
        return 2
    fi
    cp -p "$cfg" "${cfg}.bak"
    mv "$tmp" "$cfg"
}

# Override limit.context for one model, this run only unless $3 is 1. The
# inline OPENCODE_CONFIG_CONTENT fragment is schema-validated on its own, so it
# must carry the model's existing limit.output too.
oc_wrapper_set_ctx() {
    local spec="$1" size="$2" persist="$3"
    local jq_bin cfg resolved status provider_id model_slug output override base contents
    if [[ ! "$size" =~ ^[1-9][0-9]*$ ]]; then
        echo "oc: --set-ctx size must be a positive integer, got '${size}'" >&2
        return 2
    fi
    if ! jq_bin="$(command -v jq)"; then
        echo "oc: --set-ctx requires jq" >&2
        return 2
    fi
    cfg="$(oc_wrapper_config_file)"
    if [[ ! -f "$cfg" ]]; then
        echo "oc: --set-ctx: config file not found at ${cfg}" >&2
        return 2
    fi
    if ! resolved="$(oc_wrapper_resolve_target "$jq_bin" "$spec" "$cfg")"; then
        return 2
    fi
    IFS=$'\t' read -r status provider_id model_slug <<< "$resolved"
    if [[ "$status" != "OK" ]]; then
        echo "oc: ${provider_id}" >&2
        return 2
    fi
    output="$("$jq_bin" -r --arg p "$provider_id" --arg m "$model_slug" \
        '.provider[$p].models[$m].limit.output // empty' "$cfg")"
    if [[ -z "$output" ]]; then
        echo "oc: --set-ctx: ${provider_id}/${model_slug} has no limit.output in ${cfg}; cannot build a valid limit override" >&2
        return 2
    fi
    override="$("$jq_bin" -cn --arg p "$provider_id" --arg m "$model_slug" --argjson n "$size" --argjson o "$output" \
        '{provider:{($p):{models:{($m):{limit:{context:$n,output:$o}}}}}}')"
    base="${OPENCODE_CONFIG_CONTENT:-}"
    if [[ -z "$base" ]]; then
        base='{}'
    fi
    contents="$("$jq_bin" -cn --argjson a "$base" --argjson b "$override" '$a * $b')"
    export OPENCODE_CONFIG_CONTENT="$contents"
    if [[ "$persist" == "1" ]]; then
        oc_wrapper_persist_ctx "$jq_bin" "$cfg" "$provider_id" "$model_slug" "$size" || return 2
        printf '[oc] ctx: %s/%s context=%s (persisted to %s)\n' "$provider_id" "$model_slug" "$size" "$cfg" >&2
    else
        printf '[oc] ctx: %s/%s context=%s (this run)\n' "$provider_id" "$model_slug" "$size" >&2
    fi
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
        oc_wrapper_reconcile_shard "$root"
    else
        # Fail loud. A swallowed `git rev-parse` here quietly drops the shard
        # and sends the session to the default DB, where every sharded session
        # looks empty (observed: a root-locked .git + a /usr/bin/git that is
        # not the guard, so the safe.directory injection is missing and git
        # reports "dubious ownership"). Surface git's stderr and continue.
        printf '[oc] warning: could not resolve the git root for shard selection\n' >&2
        printf '[oc]   `git rev-parse --show-toplevel` said: %s\n' "$root" >&2
        printf '[oc]   opencode will use the default DB; sharded sessions may appear empty.\n' >&2
        printf '[oc]   hint: "dubious ownership" means /usr/bin/git is not the workspace guard\n' >&2
        printf '[oc]   (its safe.directory injection is missing). Reinstall the git guard, then rerun.\n' >&2
    fi
}

# Canonical opencode project id for a git root. opencode resolves the id as
# origin-remote hash first, then the first root commit (ProjectV2.resolve).
# Prints the id, or returns 1 when neither is available.
oc_wrapper_project_id() {
    local root="$1" url rest host path norm
    if url="$(git -C "$root" remote get-url origin 2>&1)"; then
        url="${url%$'\n'}"
        url="${url%$'\r'}"
        case "$url" in
            file:*) ;;
            *://*)
                rest="${url#*://}"
                rest="${rest#*@}"
                host="${rest%%/*}"
                host="${host%%:*}"
                path="${rest#*/}"
                ;;
            *:*)
                rest="${url#*@}"
                host="${rest%%:*}"
                path="${rest#*:}"
                ;;
        esac
        if [[ -n "${host:-}" && -n "${path:-}" ]]; then
            norm="$path"
            while [[ "$norm" == /* ]]; do norm="${norm#/}"; done
            case "$norm" in
                *.git/) norm="${norm%.git/}" ;;
                *.git) norm="${norm%.git}" ;;
            esac
            while [[ "$norm" == */ ]]; do norm="${norm%/}"; done
            if [[ -n "$norm" ]]; then
                printf '%s' "git-remote:${host,,}/${norm}" | sha1sum | cut -c1-40
                return 0
            fi
        fi
    fi
    if norm="$(git -C "$root" rev-list --max-parents=0 HEAD 2>&1)" && [[ -n "$norm" ]]; then
        printf '%s\n' "${norm%%$'\n'*}"
        return 0
    fi
    return 1
}

# opencode's session list is filtered by the project id resolved for the
# current process. When an origin remote is added after the first sessions,
# the id flips (root commit -> remote hash) and the older sessions disappear
# from every list. Fold every project id sharing this worktree into the id
# opencode resolves today so no session is orphaned. Idempotent: no-op unless
# a sibling project row exists. Failure only warns - opencode still runs.
oc_wrapper_reconcile_shard() {
    local root="$1" canonical data_dir db sql_dir count
    if [ -z "$(command -v sqlite3)" ]; then
        return 0
    fi
    if ! canonical="$(oc_wrapper_project_id "$root")"; then
        return 0
    fi
    sql_dir="${_OC_WRAPPER_DIR}/../sql"
    data_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/opencode"
    db="${data_dir}/${OPENCODE_DB}"
    [ -f "$db" ] || return 0
    if ! count="$(cat -- "${sql_dir}/oc_project_table_count.sql" \
        | sqlite3 "file:${db}?mode=ro" 2>&1)"; then
        return 0
    fi
    [ "$count" = "1" ] || return 0
    if ! count="$(
        {
            printf ".parameter set :root '%s'\n" "${root//\'/\'\'}"
            printf ".parameter set :canon '%s'\n" "${canonical//\'/\'\'}"
            cat -- "${sql_dir}/oc_project_sibling_count.sql"
        } | sqlite3 "file:${db}?mode=ro" 2>&1
    )"; then
        return 0
    fi
    if [[ ! "$count" =~ ^[0-9]+$ ]] || [ "$count" -eq 0 ]; then
        return 0
    fi
    if {
        printf ".parameter set :root '%s'\n" "${root//\'/\'\'}"
        printf ".parameter set :canon '%s'\n" "${canonical//\'/\'\'}"
        cat -- "${sql_dir}/oc_reconcile_project.sql"
    } | sqlite3 -cmd ".timeout 3000" "$db"; then
        printf '[oc] reconciled %s: project ids unified to %s\n' "$OPENCODE_DB" "$canonical" >&2
    else
        printf '[oc] warning: could not reconcile project ids in %s; sessions under a superseded project id stay hidden\n' "$OPENCODE_DB" >&2
    fi
}

oc_wrapper_resolve_session_db() {
    # Cross-db session resume: find the database owning $1 (a ses_* id)
    # by probing every db in the data dir. Prints nothing when absent.
    local sid="$1" data_dir f n
    if [ -z "$(command -v sqlite3)" ]; then
        return 1
    fi
    data_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/opencode"
    sid="${sid//\'/\'\'}"
    for f in "$data_dir"/*.db; do
        [ -f "$f" ] || continue
        n="$(
            {
                printf ".parameter set :sid '%s'\n" "${sid//\'/\'\'}"
                cat -- "${_OC_WRAPPER_DIR}/../sql/session_exists.sql"
            } | sqlite3 "$f"
        )"
        if [ "$n" = "1" ]; then
            export OPENCODE_DB="$(basename "$f")"
            printf '[oc] db: session owner %s (cross-db resume)\n' "$OPENCODE_DB" >&2
            return 0
        fi
    done
    return 1
}

oc_wrapper_session_arg() {
    # Echo the first ses_* argument, or nothing.
    local arg
    for arg in "$@"; do
        if [[ "$arg" =~ ^ses_[A-Za-z0-9]+$ ]]; then
            printf '%s\n' "$arg"
            return 0
        fi
    done
    return 1
}

oc_wrapper_dispatch() {
    local opencode="$1"
    local original_pwd="$2"
    local db=""
    local has_db=0
    local mono=0
    local direct=0
    local set_ctx_spec=""
    local set_ctx_size=""
    local persist_ctx=0
    local -a args=()
    shift 2

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --mono)
                mono=1
                shift
                ;;
            --set-ctx)
                if [[ $# -lt 3 ]]; then
                    echo "oc: --set-ctx requires <provider>/<model> <size>" >&2
                    return 2
                fi
                set_ctx_spec="$2"
                set_ctx_size="$3"
                shift 3
                ;;
            --persist)
                persist_ctx=1
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
        local sid
        if sid=$(oc_wrapper_session_arg "${args[@]}"); then
            oc_wrapper_resolve_session_db "$sid" || oc_wrapper_shard_db
        else
            oc_wrapper_shard_db
        fi
    fi
    if [[ $persist_ctx -eq 1 && -z "$set_ctx_spec" ]]; then
        echo "oc: --persist requires --set-ctx" >&2
        return 2
    fi
    if [[ -n "$set_ctx_spec" ]]; then
        oc_wrapper_set_ctx "$set_ctx_spec" "$set_ctx_size" "$persist_ctx" || return 2
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
