#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh" || exit 1
require_command expect
require_command awk
require_command sort

: "${WORKSPACE_AGENT_PASSWORD:?WORKSPACE_AGENT_PASSWORD is not set in $ENV_FILE}"
export WORKSPACE_SSH_PASSWORD="$WORKSPACE_AGENT_PASSWORD"
mkdir -p "$CONFIG_DIR"

REMOTE_LIST="find $(printf '%q' "$WORKSPACE_PROJECTS_DIR") -mindepth 1 -maxdepth 1 -type d -name $(printf '%q' "$WORKSPACE_PROJECT_GLOB") -print"
PROJECTS=()
while IFS= read -r project; do
    [[ -n "$project" ]] || continue
    project_name="${project##*/}"
    has_excluded_project "$project_name" && continue
    PROJECTS+=("$project")
done < <(expect "$SCRIPT_DIR/sshpw.exp" "$(ssh_target agent)" cmd "$REMOTE_LIST" | tr -d '\r' | sort)

NAMES=()
ROLES=()
DIRECTORIES=()
USED_NAMES=()
add_profile() {
    local role="$1" directory="$2" base name
    base="${directory##*/}"
    name="${base#WORKSPACE-}"
    for used in "${USED_NAMES[@]}"; do
        [[ "$used" == "$name" ]] && name="$base"
    done
    USED_NAMES+=("$name")
    NAMES+=("$name")
    ROLES+=("$role")
    DIRECTORIES+=("$directory")
}

add_profile agent "$WORKSPACE_BASE_DIR"
for project in "${PROJECTS[@]}"; do add_profile agent "$project"; done
add_profile admin "$WORKSPACE_PROJECTS_DIR"

fragment="$(mktemp)"
trap 'rm -f "$fragment" "$CONFIG_FILE.new"' EXIT
{
    printf 'profiles:\n'
    for index in "${!NAMES[@]}"; do
        name="${NAMES[$index]}"
        printf '  - name: %s\n' "$(yaml_quote "$name")"
        printf '    id: %s\n' "$(yaml_quote "local:custom:$(profile_id "$name")")"
        printf '    type: local\n    disableDynamicTitle: true\n    options:\n'
        printf '      command: %s\n      args:\n' "$(yaml_quote "$SCRIPT_DIR/run-ssh.sh")"
        printf '        - %s\n        - %s\n' "$(yaml_quote "${ROLES[$index]}")" "$(yaml_quote "${DIRECTORIES[$index]}")"
        printf '      env: {}\n      cwd: null\n      width: null\n      height: null\n      shellType: null\n      pauseAfterExit: false\n      runAsAdministrator: false\n'
    done
} > "$fragment"

if [[ -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak.$(date '+%Y%m%d%H%M%S')"
    awk -v fragment="$fragment" '
        function emit() { while ((getline line < fragment) > 0) print line; close(fragment) }
        /^profiles:[[:space:]]*(\[|\{|$)/ { if (!done) { emit(); done = 1 }; skip = 1; next }
        skip && /^[A-Za-z_]/ { skip = 0 }
        skip { next }
        { print }
        END { if (!done) emit() }
    ' "$CONFIG_FILE" > "$CONFIG_FILE.new"
else
    cp "$fragment" "$CONFIG_FILE.new"
fi
mv "$CONFIG_FILE.new" "$CONFIG_FILE"

printf '%s\n' "${NAMES[@]}" > "$PROFILES_FILE"
printf 'Wrote %d Tabby profiles to %s\n' "${#NAMES[@]}" "$CONFIG_FILE"
