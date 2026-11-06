#!/bin/bash

oc_wrapper_set_mod() {
    local spec="$1"
    local cli="${_OC_WRAPPER_DIR}/../moderator/dist/cli.js"
    if [[ ! -f "$cli" ]]; then
        echo "oc: moderator CLI is missing; run make install-moderator" >&2
        return 2
    fi
    node "$cli" models set "$spec"
}

oc_wrapper_run_mod() {
    local sid="$1" force="$2" opencode="$3"
    export AGENTCI_RUN_MOD=1
    export AGENTCI_RUN_MOD_SESSION="$sid"
    if [[ "$force" == 1 ]]; then
        export AGENTCI_RUN_MOD_FORCE=1
        printf '[oc] run-mod-force: judging the last response for %s\n' "$sid" >&2
    else
        printf '[oc] run-mod: replaying the last moderation decision for %s\n' "$sid" >&2
    fi
    exec "$opencode" --session "$sid"
}

oc_wrapper_finish_run_mod() {
    local force="$1" opencode="$2" resume_sid="$3"
    shift 3
    local run_mod_sid="" _run_mod_arg
    for _run_mod_arg in "$@"; do
        if [[ "$_run_mod_arg" =~ ^ses_[A-Za-z0-9]+$ ]]; then
            run_mod_sid="$_run_mod_arg"
        elif [[ "$_run_mod_arg" != -* ]]; then
            echo "oc: --run-mod does not take a task argument: ${_run_mod_arg}" >&2
            return 2
        fi
    done
    if [[ -n "$run_mod_sid" ]]; then
        oc_wrapper_run_mod "$run_mod_sid" "$force" "$opencode"
        return $?
    fi
    if [[ -z "$resume_sid" ]]; then
        resume_sid="$(oc_wrapper_latest_session)"
    fi
    if [[ -z "$resume_sid" ]]; then
        echo "oc: --run-mod requires a session id" >&2
        return 2
    fi
    oc_wrapper_run_mod "$resume_sid" "$force" "$opencode"
}
