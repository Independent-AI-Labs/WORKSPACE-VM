#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${WORKSPACE_AUTOMATION_ENV_FILE:-$SCRIPT_DIR/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
    printf 'error: configuration file not found: %s\n' "$ENV_FILE" >&2
    printf 'copy %s to %s and set the workspace values\n' \
        "$SCRIPT_DIR/.env.example" "$ENV_FILE" >&2
    exit 1
fi

set -a
source "$ENV_FILE" || exit 1
set +a

: "${WORKSPACE_SSH_HOST:?WORKSPACE_SSH_HOST is not set in $ENV_FILE}"
: "${WORKSPACE_SSH_PORT:=22}"
: "${WORKSPACE_AGENT_USER:=agent}"
: "${WORKSPACE_ADMIN_USER:=admin}"
: "${WORKSPACE_BASE_DIR:?WORKSPACE_BASE_DIR is not set in $ENV_FILE}"
: "${WORKSPACE_PROJECTS_DIR:=$WORKSPACE_BASE_DIR/projects}"
: "${WORKSPACE_PROJECT_GLOB:=WORKSPACE-*}"
: "${WORKSPACE_EXCLUDE_PROJECTS:=}"
: "${WORKSPACE_TABBY_COMMAND:=tabby}"

CONFIG_DIR="${WORKSPACE_TABBY_CONFIG_DIR:-}"
if [[ -z "$CONFIG_DIR" ]]; then
    case "$(uname -s)" in
        Darwin) CONFIG_DIR="$HOME/Library/Application Support/tabby" ;;
        Linux) CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/tabby" ;;
        *) printf 'error: unsupported operating system: %s\n' "$(uname -s)" >&2; exit 1 ;;
    esac
fi
CONFIG_FILE="$CONFIG_DIR/config.yaml"
PROFILES_FILE="$SCRIPT_DIR/profiles.txt"
LOG_FILE="$SCRIPT_DIR/open-workspaces.log"

require_command() {
    local command_path
    if command_path="$(command -v "$1" 2>&1)" && [[ -n "$command_path" ]]; then
        return 0
    else
        printf 'error: required command not found: %s\n' "$1" >&2
        exit 1
    fi
}

yaml_quote() {
    local value="$1"
    value=${value//\'/\'\'}
    printf "'%s'" "$value"
}

profile_id() {
    local value="$1"
    value=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-')
    value=${value##-}
    value=${value%%-}
    printf '%s' "${value:-workspace}"
}

has_excluded_project() {
    local candidate="$1" excluded
    for excluded in $WORKSPACE_EXCLUDE_PROJECTS; do
        [[ "$candidate" == "$excluded" ]] && return 0
    done
    return 1
}

ssh_target() {
    local role="$1"
    case "$role" in
        agent) printf '%s@%s' "$WORKSPACE_AGENT_USER" "$WORKSPACE_SSH_HOST" ;;
        admin) printf '%s@%s' "$WORKSPACE_ADMIN_USER" "$WORKSPACE_SSH_HOST" ;;
        *) printf 'error: unknown role: %s\n' "$role" >&2; return 1 ;;
    esac
}
