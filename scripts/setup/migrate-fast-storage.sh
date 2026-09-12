#!/bin/bash
set -euo pipefail

# migrate-fast-storage.sh
#
# Agent-side fast-storage migration onto the storage provisioned by
# configure-fast-storage.sh. COPY-ONLY INVARIANT: nothing is moved,
# renamed, or deleted - every original stays at its old location until
# an operator cleans it up manually. Cleanup is NEVER automated.
#
#   1. podman rootless store: the 110G copy itself CANNOT run here - the
#      store contains subuid-owned trees (uid 100000+) that the agent
#      cannot read. The copy runs as ROOT in the operator script
#      (/tmp/opencode/relieve-and-migrate.sh) before this script is
#      invoked; this section only verifies the copy exists and then
#      flips ~/.config/containers/storage.conf to the new graphroot.
#      The old store stays fully intact at ~/.local/share/containers.
#   2. llamafile weights: copy repo models/ -> $WS_FAST_DIR/models/
#      (original untouched) + WS_MODELS_DIR env config.
#   3. QEMU overlays: copy repo .vms/ -> $WS_FAST_DIR/qemu/ (original
#      untouched) + WS_VM_DIR env config. Skipped while a guest runs.
#   4. caches: COPY ~/.cargo and ~/.cache/uv to $WS_FAST_DIR/caches/
#      (originals untouched) + CARGO_HOME / UV_CACHE_DIR env configs.
#
# Env overrides (user-manageable):
#   WS_FAST_DIR  (default /mnt/ws-fast)
#
# Idempotent: re-runs skip completed steps (re-rsync refreshes copies).
# Dry-run:  --dry-run prints every action without changing anything.
#
# Usage:
#   bash scripts/setup/migrate-fast-storage.sh --dry-run
#   bash scripts/setup/migrate-fast-storage.sh
#   make migrate-fast-storage MIGRATE_ARGS='--dry-run'

WS_FAST_DIR="${WS_FAST_DIR:-/mnt/ws-fast}"
DRY_RUN=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            sed -n '3,33p' "$0"
            exit 0
            ;;
        *)
            printf 'error: unknown argument: %s\n' "$1" >&2
            exit 1
            ;;
    esac
    shift
done

if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: run as the agent user, not root. The root-side steps" >&2
    echo "(mount provisioning, subuid store copy) live in the operator script." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

run() {
    if [ "$DRY_RUN" = true ]; then
        echo "    DRY-RUN: $*"
    else
        "$@"
    fi
}

have_pids() {
    pgrep "$@" | grep -q .
}

echo "=== Fast-storage data migration -> $WS_FAST_DIR ==="
[ "$DRY_RUN" = true ] && echo "    (dry-run: no changes will be made)"
echo ""

# --- 0. Preflight ---
if ! findmnt -n -o TARGET "$WS_FAST_DIR" | grep -qx "$WS_FAST_DIR"; then
    echo "ERROR: $WS_FAST_DIR is not mounted. Run the root provisioning first:" >&2
    echo "    one-time: docs/OPS-FAST-STORAGE.md phase 1 (typed at a root prompt)" >&2
    echo "    then:     sudo make configure-fast-storage" >&2
    exit 1
fi
if [ "$(findmnt -no FSTYPE "$WS_FAST_DIR")" != "ext4" ]; then
    echo "ERROR: $WS_FAST_DIR is not ext4" >&2
    exit 1
fi
_probe="$WS_FAST_DIR/.migration-probe"
if ! touch "$_probe" 2>&1; then
    echo "ERROR: $WS_FAST_DIR is not writable by $(id -un)" >&2
    exit 1
fi
rm -f "$_probe"

# --- 1. Podman rootless store: verify root-side copy, flip graphroot ---
echo "[1/4] Podman store (graphroot + volumes) ..."
PODMAN_CONF_DIR="$HOME/.config/containers"
PODMAN_CONF="$PODMAN_CONF_DIR/storage.conf"
PODMAN_OLD="$HOME/.local/share/containers"
PODMAN_NEW="$WS_FAST_DIR/containers"
if [ -f "$PODMAN_CONF" ] && grep -q "^graphroot *= *\"$PODMAN_NEW/storage\"" "$PODMAN_CONF"; then
    echo "    storage.conf already points at $PODMAN_NEW/storage - skipped"
else
    _busy=0
    if have_pids -x conmon; then
        _busy=1
    fi
    if have_pids -f 'podman( |$)'; then
        _busy=1
    fi
    if [ "$_busy" -eq 1 ]; then
        echo "ERROR: podman/conmon processes are running; stop all containers first:" >&2
        echo "    podman ps; podman stop ...  (or compose down for each stack)" >&2
        exit 1
    fi
    # The subuid store copy must have been done by the root operator
    # script; refuse to point podman at a missing/partial store.
    # (podman 5.x uses db.sql; older releases used libpod/bolt_state.db)
    if [ ! -f "$PODMAN_NEW/storage/db.sql" ] && [ ! -f "$PODMAN_NEW/storage/libpod/bolt_state.db" ]; then
        echo "ERROR: $PODMAN_NEW/storage/libpod/bolt_state.db missing." >&2
        echo "The subuid-owned store copy cannot run as agent. Run the ROOT" >&2
        echo "operator script first (it rsyncs the store as root):" >&2
        echo "    sudo bash /tmp/opencode/relieve-and-migrate.sh" >&2
        exit 1
    fi
    run mkdir -p "$PODMAN_CONF_DIR"
    if [ "$DRY_RUN" = true ]; then
        echo "    DRY-RUN: write $PODMAN_CONF (graphroot=$PODMAN_NEW/storage)"
    else
        _uid="$(id -u)"
        {
            printf '[storage]\n'
            printf 'driver = "overlay"\n'
            printf 'runroot = "/run/user/%s/containers"\n' "$_uid"
            printf 'graphroot = "%s/storage"\n' "$PODMAN_NEW"
        } > "$PODMAN_CONF"
        echo "    wrote $PODMAN_CONF"
    fi
    echo "    COPY-ONLY: old store stays intact at $PODMAN_OLD (manual cleanup)"
    echo "    OPERATOR VERIFICATION (as agent; .boot-linux podman wrapper"
    echo "    blocks system migrate by design - do NOT run it):"
    echo "        podman info | grep -i graphroot"
    echo "        podman images && podman volume ls"
fi

# --- 2+3. Repo data trees (models, QEMU overlays) ---
echo "[2/4] llamafile weights (models/) ..."
if [ -d "$REPO_ROOT/models" ]; then
    run rsync -aHAX "$REPO_ROOT/models/" "$WS_FAST_DIR/models/"
    echo "    copied to $WS_FAST_DIR/models (original untouched; tracked .args stay in repo)"
else
    echo "    no $REPO_ROOT/models - skipped"
fi
echo "[3/4] QEMU overlays (.vms/) ..."
VMS_MIGRATED=false
if [ -d "$REPO_ROOT/.vms" ]; then
    _live_vms=""
    _live_vms="$(ps -eo args= | grep -F "$REPO_ROOT/.vms/" | grep -F qemu-system | grep -v grep)" || _live_vms=""
    if [ -n "$_live_vms" ]; then
        echo "    SKIP: a live QEMU guest is using disks under $REPO_ROOT/.vms."
        echo "    Copying now would create a stale copy that WS_VM_DIR later"
        echo "    points at (split-brain with the running guest). Stop the guest"
        echo "    (make vm-stop <uuid>), then re-run this script."
    else
        run rsync -aHAX "$REPO_ROOT/.vms/" "$WS_FAST_DIR/qemu/"
        VMS_MIGRATED=true
        echo "    copied to $WS_FAST_DIR/qemu (original untouched)"
    fi
else
    echo "    no $REPO_ROOT/.vms - skipped"
fi

# --- 4. Caches: copy-only + env configs (originals untouched) ---
echo "[4/4] Caches (cargo, uv) ..."
CARGO_MIGRATED=false
UV_MIGRATED=false
if [ -d "$HOME/.cargo" ]; then
    run rsync -aHAX "$HOME/.cargo/" "$WS_FAST_DIR/caches/cargo/"
    CARGO_MIGRATED=true
    echo "    copied $HOME/.cargo -> $WS_FAST_DIR/caches/cargo (original untouched)"
else
    echo "    no $HOME/.cargo - skipped"
fi
if [ -d "$HOME/.cache/uv" ]; then
    run rsync -aHAX "$HOME/.cache/uv/" "$WS_FAST_DIR/caches/uv/"
    UV_MIGRATED=true
    echo "    copied $HOME/.cache/uv -> $WS_FAST_DIR/caches/uv (original untouched)"
else
    echo "    no $HOME/.cache/uv - skipped"
fi

# --- 5. Persist env path configs in ~/.bashrc (marker-guarded) ---
BASHRC_MARK_BEGIN="# --- workspace fast-storage paths begin ---"
BASHRC_MARK_END="# --- workspace fast-storage paths end ---"
if grep -q "^$BASHRC_MARK_BEGIN" "$HOME/.bashrc"; then
    echo ""
    echo "bashrc fast-storage block already present - skipped"
elif [ "$DRY_RUN" = true ]; then
    echo ""
    echo "DRY-RUN: append env block to ~/.bashrc:"
    echo "    $BASHRC_MARK_BEGIN"
    echo "    export WS_MODELS_DIR=\"$WS_FAST_DIR/models\""
    if [ "$VMS_MIGRATED" = true ]; then
        echo "    export WS_VM_DIR=\"$WS_FAST_DIR/qemu\""
    fi
    if [ "$CARGO_MIGRATED" = true ]; then
        echo "    export CARGO_HOME=\"$WS_FAST_DIR/caches/cargo\""
    fi
    if [ "$UV_MIGRATED" = true ]; then
        echo "    export UV_CACHE_DIR=\"$WS_FAST_DIR/caches/uv\""
    fi
    echo "    $BASHRC_MARK_END"
else
    {
        printf '\n%s\n' "$BASHRC_MARK_BEGIN"
        printf 'export WS_MODELS_DIR="%s/models"\n' "$WS_FAST_DIR"
        if [ "$VMS_MIGRATED" = true ]; then
            printf 'export WS_VM_DIR="%s/qemu"\n' "$WS_FAST_DIR"
        fi
        if [ "$CARGO_MIGRATED" = true ]; then
            printf 'export CARGO_HOME="%s/caches/cargo"\n' "$WS_FAST_DIR"
        fi
        if [ "$UV_MIGRATED" = true ]; then
            printf 'export UV_CACHE_DIR="%s/caches/uv"\n' "$WS_FAST_DIR"
        fi
        printf '%s\n' "$BASHRC_MARK_END"
    } >> "$HOME/.bashrc"
    echo ""
    echo "appended fast-storage env exports to ~/.bashrc"
fi

echo ""
echo "=== Done (copy-only; nothing was moved or deleted) ==="
echo "Originals kept at their old locations for manual cleanup:"
echo "  - $PODMAN_OLD"
echo "  - $REPO_ROOT/models, $REPO_ROOT/.vms"
echo "  - $HOME/.cargo, $HOME/.cache/uv"
