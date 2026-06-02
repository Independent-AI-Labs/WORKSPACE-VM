#!/usr/bin/env bash
# ami_gitleaks_sweep.sh — weekly gitleaks history scan across every repo in
# the workspace. Emails the operator on any finding so re-leaks get caught
# early, instead of waiting for the next pre-commit run on a touched repo.
#
# Mirrors the `ami_failure_notify.sh` send pattern (himalaya account
# `polymarket`, To = AMI_FAILURE_NOTIFY_TO or independentailabs@gmail.com).
# Per-repo `.gitleaksignore` allowlists are honored automatically by gitleaks
# itself, so documented false positives stay quiet.
#
# Exit codes:
#   0  — all repos clean
#   1  — at least one finding (email sent if himalaya available)
#   2  — bad invocation / setup error
#   3  — himalaya unavailable but findings present (operator MUST see logs)
#
# Run via cron weekly:
#   cron add "0 4 * * 1" "$HOME/AMI-AGENTS/scripts/services/ami_gitleaks_sweep.sh" --label gitleaks-sweep

set -euo pipefail

readonly WORKSPACE="${AMI_WORKSPACE_ROOT:-${HOME}/AMI-AGENTS}"
readonly GITLEAKS_BIN="${AMI_GITLEAKS_BIN:-${WORKSPACE}/.boot-linux/bin/gitleaks}"
readonly TO_ADDR="${AMI_FAILURE_NOTIFY_TO:-independentailabs@gmail.com}"
readonly HIMALAYA_BIN="${AMI_HIMALAYA_BIN:-${WORKSPACE}/.boot-linux/bin/himalaya}"
readonly HIMALAYA_ACCOUNT="${AMI_FAILURE_NOTIFY_ACCOUNT:-polymarket}"
readonly REPORT_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/ami/gitleaks-sweep"
readonly TIMESTAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"

# --dry-run: scan + report locally but never invoke himalaya. Useful for
# manual `bash ami_gitleaks_sweep.sh --dry-run` after adding new
# .gitleaksignore entries to confirm zero findings before unleashing the
# weekly cron's mail.
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" || "${AMI_GITLEAKS_SWEEP_DRY_RUN:-}" == "1" ]]; then
    DRY_RUN=1
fi

log() {
    printf '[ami-gitleaks-sweep] %s\n' "$*" >&2
}

die() {
    local code="$1"; shift
    log "ERROR: $*"
    exit "$code"
}

[[ -x "$GITLEAKS_BIN" ]] || die 2 "gitleaks binary not executable: $GITLEAKS_BIN"
[[ -d "$WORKSPACE" ]] || die 2 "workspace root not a directory: $WORKSPACE"

mkdir -p "$REPORT_DIR"
readonly RUN_DIR="${REPORT_DIR}/${TIMESTAMP}"
mkdir -p "$RUN_DIR"

# Enumerate repos: AMI-AGENTS root + every projects/* that has its own .git.
# Sub-submodules (rust-ta inside RUST-TRADING) are scanned by their parent's
# detect run because gitleaks walks the working tree; no special handling.
repos=( "$WORKSPACE" )
for d in "$WORKSPACE"/projects/*/; do
    [[ -d "${d}.git" ]] && repos+=( "${d%/}" )
done

log "Scanning ${#repos[@]} repos at $TIMESTAMP"

total_findings=0
report_summary=""
for repo in "${repos[@]}"; do
    repo_name="$(basename "$repo")"
    out_json="${RUN_DIR}/${repo_name}.json"
    log "  scanning $repo_name"
    rc=0
    "$GITLEAKS_BIN" detect \
        --source "$repo" \
        --no-banner \
        --redact \
        --report-path "$out_json" \
        --exit-code 1 \
        > "${RUN_DIR}/${repo_name}.log" 2>&1 || rc=$?
    if [[ $rc -eq 0 ]]; then
        report_summary+="  ${repo_name}: clean"$'\n'
    elif [[ $rc -eq 1 ]]; then
        # gitleaks exits 1 on findings (after .gitleaksignore filter)
        finding_count="$(python3 -c "import json,sys; print(len(json.load(open('$out_json'))))" 2>/dev/null || echo "?")"
        report_summary+="  ${repo_name}: ${finding_count} finding(s) — see ${out_json}"$'\n'
        total_findings=$((total_findings + 1))
    else
        # Runtime error — gitleaks itself crashed, not a finding signal.
        report_summary+="  ${repo_name}: SCAN ERROR (rc=$rc) — see ${RUN_DIR}/${repo_name}.log"$'\n'
        total_findings=$((total_findings + 1))
    fi
done

log "$total_findings repo(s) flagged"
log "report dir: $RUN_DIR"

if [[ $total_findings -eq 0 ]]; then
    # Prune empty run dirs older than 4 weeks to keep the report-dir bounded.
    # Cleanup old empty run dirs; find returns 0 when no matches, so
    # this is loud-on-real-failure without needing a redirect.
    find "$REPORT_DIR" -maxdepth 1 -type d -mtime +28 -exec rm -rf {} +
    exit 0
fi

if [[ $DRY_RUN -eq 1 ]]; then
    log "DRY-RUN: skipping email; findings logged at $RUN_DIR"
    log "summary:"
    while IFS= read -r line; do log "$line"; done <<< "$report_summary"
    exit 1
fi

if [[ ! -x "$HIMALAYA_BIN" ]]; then
    log "FINDINGS PRESENT but himalaya not on PATH at $HIMALAYA_BIN; manual inspection required"
    exit 3
fi

readonly SUBJECT="[AMI] gitleaks weekly sweep: ${total_findings} repo(s) flagged (${TIMESTAMP})"
body=$(cat <<EOF
gitleaks weekly history sweep run at $TIMESTAMP found new (or unallowlisted) secrets in $total_findings of ${#repos[@]} workspace repos.

Per-repo summary:
$report_summary

Reports: $RUN_DIR/

Action: review each *.json + *.log file for the offending pattern. If a finding is a documented false positive, add its fingerprint to the repo-local .gitleaksignore. If a finding is a real credential, follow projects/docs/RUNBOOK-CREDENTIAL-LEAK.md (rotate first, then scrub).
EOF
)

timeout 60s "$HIMALAYA_BIN" message send -a "$HIMALAYA_ACCOUNT" <<EOF || die 3 "himalaya send failed; report at $RUN_DIR"
From: independentailabs@gmail.com
To: $TO_ADDR
Subject: $SUBJECT

$body
EOF

log "notification email sent to $TO_ADDR"
exit 1
