#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh" || exit 1

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1
log "========== launch =========="

if [[ ! -s "$PROFILES_FILE" ]]; then
    log "profile list missing; syncing from host"
    "$SCRIPT_DIR/sync-tabby-profiles.sh"
fi

case "$(uname -s)" in
    Darwin)
        open -a "$WORKSPACE_TABBY_COMMAND"
        opener=(open)
        ;;
    Linux)
        require_command "$WORKSPACE_TABBY_COMMAND"
        "$WORKSPACE_TABBY_COMMAND" >> "$LOG_FILE" 2>&1 &
        opener=(xdg-open)
        require_command "${opener[0]}"
        ;;
    *) printf 'error: unsupported operating system: %s\n' "$(uname -s)" >&2; exit 1 ;;
esac

sleep 2
opened=0
while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    "${opener[@]}" "tabby://profile?profileName=$name"
    log "opened tab: $name"
    opened=$((opened + 1))
    sleep 1
done < "$PROFILES_FILE"
log "opened $opened workspace tabs"
