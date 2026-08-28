#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh" || exit 1

ROLE="${1:?usage: run-ssh.sh <agent|admin> <directory>}"
DIRECTORY="${2:?usage: run-ssh.sh <agent|admin> <directory>}"
require_command expect

case "$ROLE" in
    agent) : "${WORKSPACE_AGENT_PASSWORD:?WORKSPACE_AGENT_PASSWORD is not set in $ENV_FILE}"; export WORKSPACE_SSH_PASSWORD="$WORKSPACE_AGENT_PASSWORD" ;;
    admin) : "${WORKSPACE_ADMIN_PASSWORD:?WORKSPACE_ADMIN_PASSWORD is not set in $ENV_FILE}"; export WORKSPACE_SSH_PASSWORD="$WORKSPACE_ADMIN_PASSWORD" ;;
    *) printf 'error: unknown role: %s (expected agent or admin)\n' "$ROLE" >&2; exit 1 ;;
esac

exec expect "$SCRIPT_DIR/sshpw.exp" "$(ssh_target "$ROLE")" "$ROLE" "$DIRECTORY"
