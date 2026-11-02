#!/bin/bash
# Persistent security review. Resumes one oc session per repo and writes
# findings under WORKSPACE-VM/docs/audits/. Does not change product code.
set -euo pipefail

ROOT="${WORKSPACE_ROOT:-${HOME}/WORKSPACE-VM}"
REPO="${1:-${ROOT}/projects/WORKSPACE-GATEWAY}"
REPO="$(cd "$REPO" && pwd)"
MODEL="${SECURITY_REVIEW_MODEL:-workspace-gw-grok-passthrough/grok-4.7}"
AUDITS="${ROOT}/docs/audits"
STATE_DIR="${ROOT}/scripts/state"
SQL_DIR="${ROOT}/workspace/sql"
mkdir -p "$AUDITS" "$STATE_DIR"
slug="$(printf '%s' "$REPO" | sha256sum | cut -c1-12)"
state="${STATE_DIR}/security-review-${slug}.session"
log="${STATE_DIR}/security-review-${slug}.jsonl"
db="security-review-${slug}.db"

prompt_file="${ROOT}/scripts/security-review-prompt.txt"
prompt="$(cat "$prompt_file")"$'\n'"Repository: ${REPO}"$'\n'"Audit directory: ${AUDITS}"

args=(--db "$db" -- run -m "$MODEL" --auto --format json --variant low --title "security-review ${slug}")
if [[ -f "$state" ]]; then
  sid="$(cat "$state")"
  args+=(--session "$sid")
  printf '[security-review] resume %s\n' "$sid" >&2
else
  printf '[security-review] new session\n' >&2
fi

oc "${args[@]}" "$prompt" | tee -a "$log"
ret=${PIPESTATUS[0]}
if [[ "$ret" -ne 0 ]]; then
  printf '[security-review] oc failed with exit %s\n' "$ret" >&2
  exit "$ret"
fi
sid="$(cat "${SQL_DIR}/sec_review_latest_session.sql" | sqlite3 "${HOME}/.local/share/opencode/${db}")"
if [[ -n "${sid}" ]]; then
  printf '%s\n' "$sid" > "$state"
fi
continues="$(cat "${SQL_DIR}/sec_review_compaction_count.sql" | sqlite3 "${HOME}/.local/share/opencode/${db}")"
printf '[security-review] session=%s compaction_continue=%s log=%s\n' "$sid" "$continues" "$log" >&2
