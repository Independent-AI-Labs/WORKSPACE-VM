#!/bin/bash
# Thinking-effort helpers for the opencode wrapper. Sourced by
# opencode-wrapper.sh; expects oc_wrapper_config_file and OPENCODE_DB.

# Seed the thinking effort for every configured model in opencode's
# per-model variant store (state/opencode/model.json). opencode reads that
# map when a session starts and when the user switches models, so seeding all
# keys makes the choice hold across a runtime switch too. The requested
# variant wins when the model defines it; otherwise the minimum non-off
# variant is used. "none"/"off" is never selected.
oc_wrapper_apply_variant() {
    local target="${OC_THINKING_EFFORT:-low}"
    local jq_bin cfg state model_json tmp updates count
    if ! jq_bin="$(command -v jq)"; then
        echo "oc: thinking effort skipped: jq not found" >&2
        return 0
    fi
    cfg="$(oc_wrapper_config_file)"
    if [[ ! -f "$cfg" ]]; then
        return 0
    fi
    state="${XDG_STATE_HOME:-${HOME}/.local/state}/opencode"
    model_json="${state}/model.json"
    updates="$("$jq_bin" -c --arg target "$target" '
        ["minimal", "low", "medium", "high", "max", "xhigh", "off", "none"] as $order
        | [ (.provider // {}) | to_entries[] | .key as $p
            | (.value.models // {}) | to_entries[]
            | (.value.variants // {}) as $vs
            | select(($vs | type) == "object" and ($vs | length) > 0)
            | { key: ($p + "/" + .key), names: ($vs | keys) } ]
        | map(
            (.) as $m
            | ($m.names) as $n
            | (if ($n | index($target)) then $target
               else ([ $order[] | select(. as $v | ($n | index($v)) != null) ] | first)
               end) as $chosen
            | select($chosen != null)
            | select(($chosen == "off" or $chosen == "none") | not)
            | { ($m.key): $chosen })
        | add // {}
    ' "$cfg")"
    if [[ -z "$updates" || "$updates" == "{}" ]]; then
        return 0
    fi
    mkdir -p "$state"
    tmp="$(mktemp "${model_json}.XXXXXX")"
    if [[ -f "$model_json" ]]; then
        if ! "$jq_bin" --argjson u "$updates" '.variant = ((.variant // {}) + $u)' "$model_json" > "$tmp"; then
            rm -f "$tmp"
            echo "oc: thinking effort skipped: ${model_json} is not valid JSON" >&2
            return 0
        fi
    elif ! "$jq_bin" -n --argjson u "$updates" '{variant: $u}' > "$tmp"; then
        rm -f "$tmp"
        echo "oc: thinking effort skipped: could not build ${model_json}" >&2
        return 0
    fi
    chmod 600 "$tmp"
    mv "$tmp" "$model_json"
    count="$("$jq_bin" -rn --argjson u "$updates" '$u | length')"
    printf '[oc] thinking effort: %s variants set to %s\n' "$count" "$target" >&2
}

# Echo the effort variant a model should use: the requested one when the model
# defines it, else the minimum non-off variant. Empty when undecidable.
oc_wrapper_effort_for_model() {
    local jq_bin="$1" cfg="$2" provider="$3" model="$4" requested="$5"
    "$jq_bin" -r --arg p "$provider" --arg m "$model" --arg target "$requested" '
        ["minimal", "low", "medium", "high", "max", "xhigh", "off", "none"] as $order
        | ((.provider[$p].models[$m].variants // {}) | keys) as $n
        | if ($n | length) == 0 then ""
          elif ($n | index($target)) then $target
          else ([ $order[] | select(. as $v | ($n | index($v)) != null) ] | first // "")
          end
        | select(. != "off" and . != "none")
    ' "$cfg"
}

# A resumed session keeps its stored model variant; opencode never re-reads the
# per-model store for it. Rewrite the stored variant so the resumed session
# reports and uses the requested thinking effort.
oc_wrapper_apply_session_variant() {
    local sid="$1" effort="$2"
    local jq_bin cfg db_path sqlite_bin model_json provider model chosen
    if ! jq_bin="$(command -v jq)"; then
        echo "oc: session variant skipped: jq not found" >&2
        return 0
    fi
    if ! sqlite_bin="$(command -v sqlite3)"; then
        echo "oc: session variant skipped: sqlite3 not found" >&2
        return 0
    fi
    cfg="$(oc_wrapper_config_file)"
    if [[ ! -f "$cfg" ]]; then
        return 0
    fi
    db_path="${XDG_DATA_HOME:-${HOME}/.local/share}/opencode/${OPENCODE_DB:-opencode.db}"
    if [[ ! -f "$db_path" ]]; then
        return 0
    fi
    model_json="$(
        {
            printf ".parameter set :sid '%s'\n" "${sid//\'/\'\'}"
            cat -- "${_OC_WRAPPER_DIR}/../sql/oc_session_model.sql"
        } | "$sqlite_bin" "$db_path"
    )"
    if [[ -z "$model_json" ]]; then
        echo "oc: session variant skipped: ${sid} not found in ${db_path}" >&2
        return 0
    fi
    provider="$("$jq_bin" -r '.providerID // empty' <<< "$model_json")"
    model="$("$jq_bin" -r '.id // .modelID // empty' <<< "$model_json")"
    if [[ -z "$provider" || -z "$model" ]]; then
        return 0
    fi
    chosen="$(oc_wrapper_effort_for_model "$jq_bin" "$cfg" "$provider" "$model" "$effort")"
    if [[ -z "$chosen" ]]; then
        return 0
    fi
    if [[ "$("$jq_bin" -r '.variant // empty' <<< "$model_json")" == "$chosen" ]]; then
        return 0
    fi
    {
        printf ".parameter set :sid '%s'\n" "${sid//\'/\'\'}"
        printf ".parameter set :variant '%s'\n" "${chosen//\'/\'\'}"
        cat -- "${_OC_WRAPPER_DIR}/../sql/oc_session_set_variant.sql"
    } | "$sqlite_bin" "$db_path"
    printf '[oc] session %s: variant %s\n' "$sid" "$chosen" >&2
}

# Echo the requested effort variant, refusing off/none.
oc_wrapper_requested_effort() {
    local requested="${OC_THINKING_EFFORT:-low}"
    case "$requested" in
        off|none|"") printf 'low\n' ;;
        *) printf '%s\n' "$requested" ;;
    esac
}

# Echo the newest top-level session id, or nothing.
oc_wrapper_latest_session() {
    local sqlite_bin db_path
    if ! sqlite_bin="$(command -v sqlite3)"; then
        return 0
    fi
    db_path="${XDG_DATA_HOME:-${HOME}/.local/share}/opencode/${OPENCODE_DB:-opencode.db}"
    if [[ ! -f "$db_path" ]]; then
        return 0
    fi
    cat -- "${_OC_WRAPPER_DIR}/../sql/oc_latest_session.sql" | "$sqlite_bin" "$db_path"
}

# Echo 0 when the args ask to resume a session.
oc_wrapper_resumes_session() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            -c|--continue|-s|--session|--session=*) return 0 ;;
        esac
    done
    return 1
}

# Echo 0 when the args already carry an explicit variant.
oc_wrapper_has_variant_arg() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            --variant|--variant=*) return 0 ;;
        esac
    done
    return 1
}
