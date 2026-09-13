#!/bin/bash
set -euo pipefail

# configure-fast-storage.sh
#
# Provisions the second NVMe as fast, unencrypted ext4 storage for the
# IO-heavy trees (podman graphroot + volumes, llamafile weights, QEMU
# overlays, cargo/uv caches). Motivation: the 2026-09-11 stalls showed
# every workload sharing one dm-crypt write queue on nvme0n1 (dm w_await
# 7.5s, IO PSI 94% while the raw NVMe sat at 32% util).
#
# DANGER: the one-time disk wipe/partition/format step is NOT in this
# script. The shell guard (REQ-SHG-300, config/shell_guard_policy.yaml)
# hard-blocks partition tools inside any executed script body, root
# included, by design. Those commands live in docs/OPS-FAST-STORAGE.md
# and must be typed interactively at a root prompt (the sanctioned
# operator channel). This script runs before AND after that step:
# before - it detects the unprovisioned disk and points at the runbook;
# after - it mounts, persists fstab, lays out directories, and relocates
# swap off the encrypted root.
#
# Idempotent: re-runs skip everything already in the desired state.
# Dry-run:    --dry-run prints every action without executing anything.
#
# Usage:
#   sudo bash scripts/setup/configure-fast-storage.sh --dry-run
#   sudo bash scripts/setup/configure-fast-storage.sh
#   sudo make configure-fast-storage FAST_STORAGE_ARGS='--dry-run'
#
# Env overrides (user-manageable):
#   FAST_DISK    (default /dev/nvme1n1)
#   FAST_MOUNT   (default /mnt/ws-fast)
#   FAST_LABEL   (default ws-fast)
#   SWAP_FAST_GB (default 32; size of the unencrypted swap file on fast
#                 storage that replaces the LUKS-encrypted /swap*.img)

FAST_DISK="${FAST_DISK:-/dev/nvme1n1}"
FAST_MOUNT="${FAST_MOUNT:-/mnt/ws-fast}"
FAST_LABEL="${FAST_LABEL:-ws-fast}"
SWAP_FAST_GB="${SWAP_FAST_GB:-32}"
DRY_RUN=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            sed -n '3,25p' "$0"
            exit 0
            ;;
        *)
            printf 'error: unknown argument: %s\n' "$1" >&2
            exit 1
            ;;
    esac
    shift
done

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script requires root. Run with: sudo bash $0" >&2
    exit 1
fi

# Data-owner resolution: the workspace checkout owner, never SUDO_USER
# (operators sudo from their own accounts, e.g. admin != agent, which
# chowned dirs to the wrong user in the 2026-09-12 run). The workspace
# root comes from WS_ROOT (set by callers) with a hardcoded default,
# verified against the pyproject.toml workspace marker - no BASH_SOURCE
# or pwd dancing (both proved unreliable under operator root shells).
# A blank or root resolution is a hard error, never an unlogged chown.
_DEF_ROOT="$(getent passwd agent | cut -d: -f6)/WORKSPACE-VM"
WS_ROOT="${WS_ROOT:-$_DEF_ROOT}"
if [ ! -f "$WS_ROOT/pyproject.toml" ]; then
    echo "ERROR: $WS_ROOT is not the workspace checkout (pyproject.toml missing)." >&2
    exit 1
fi
TARGET_USER="$(stat -c '%U' "$WS_ROOT/pyproject.toml")"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
    echo "ERROR: checkout owner at $WS_ROOT resolved to '$TARGET_USER'; refusing." >&2
    exit 1
fi
case "$FAST_DISK" in
    *nvme*|*md*|*vd*) PART="${FAST_DISK}p1" ;;
    *) PART="${FAST_DISK}1" ;;
esac

run() {
    if [ "$DRY_RUN" = true ]; then
        echo "    DRY-RUN: $*"
    else
        "$@"
    fi
}

is_mounted_at() {
    findmnt -n -o TARGET "$1" | grep -qx "$1"
}

echo "=== Fast-storage provisioning ($FAST_DISK -> $FAST_MOUNT) ==="
[ "$DRY_RUN" = true ] && echo "    (dry-run: no changes will be made)"
echo ""

# --- 0. Safety gates ---
if [ ! -b "$FAST_DISK" ]; then
    echo "ERROR: $FAST_DISK is not a block device" >&2
    exit 1
fi
ROOT_PART="$(findmnt -no SOURCE /)"
ROOT_DISK="/dev/$(lsblk -no PKNAME "$ROOT_PART")"
if [ "$ROOT_DISK" = "$FAST_DISK" ]; then
    echo "ERROR: $FAST_DISK carries the root filesystem ($ROOT_PART); refusing" >&2
    exit 1
fi
_mounted_parts=""
_mounted_parts="$(lsblk -nr -o MOUNTPOINTS "$FAST_DISK" | grep -v '^$')" || _mounted_parts=""
if [ -n "$_mounted_parts" ] && ! printf '%s\n' "$_mounted_parts" | grep -qx "$FAST_MOUNT"; then
    echo "ERROR: $FAST_DISK has mounted partitions:" >&2
    printf '    %s\n' "$_mounted_parts" >&2
    echo "Refusing to wipe a disk with foreign mounts" >&2
    exit 1
fi

# --- 1. Partition + filesystem (skip when already provisioned) ---
echo "[1/5] Partition + filesystem on $FAST_DISK ..."
_st=0
_cur_fs="$(blkid -s TYPE -o value "$PART" 2>&1)" || _st=$?
_cur_label=""
if [ "$_st" -eq 0 ]; then
    _cur_label="$(blkid -s LABEL -o value "$PART" 2>&1)" || _cur_label=""
fi
if [ "$_cur_fs" = "ext4" ] && [ "$_cur_label" = "$FAST_LABEL" ]; then
    echo "    already provisioned (ext4 label=$FAST_LABEL) - skipped"
else
    echo "ERROR: $PART is not a $FAST_LABEL ext4 disk yet." >&2
    echo "" >&2
    echo "Partition tools are hard-blocked inside scripts by the shell guard" >&2
    echo "(REQ-SHG-300). Run the three one-time provisioning commands from the" >&2
    echo "operator runbook INTERACTIVELY at a root prompt:" >&2
    echo "    docs/OPS-FAST-STORAGE.md  (section: one-time provision)" >&2
    echo "" >&2
    echo "Then re-run this script: it mounts, persists fstab, lays out the" >&2
    echo "directory tree, and relocates swap off the encrypted root." >&2
    exit 1
fi

# --- 2. Mount + fstab ---
echo "[2/5] Mount $FAST_MOUNT ..."
if is_mounted_at "$FAST_MOUNT"; then
    echo "    already mounted - skipped"
else
    run mkdir -p "$FAST_MOUNT"
    run mount "$PART" "$FAST_MOUNT"
fi
_fs_type="$(findmnt -no FSTYPE "$FAST_MOUNT")"
if [ "$_fs_type" != "ext4" ]; then
    echo "ERROR: $FAST_MOUNT is $_fs_type, expected ext4" >&2
    exit 1
fi
_uuid=""
_uuid_st=0
_uuid="$(blkid -s UUID -o value "$PART" 2>&1)" || _uuid_st=$?
if [ "$_uuid_st" -ne 0 ] || [ -z "$_uuid" ]; then
    echo "ERROR: could not read UUID of $PART: $_uuid" >&2
    exit 1
fi
if grep -q "^[^#]*[[:space:]]${FAST_MOUNT}[[:space:]]" /etc/fstab; then
    echo "    already in /etc/fstab - skipped"
else
    if [ "$DRY_RUN" = true ]; then
        echo "    DRY-RUN: append to /etc/fstab: UUID=$_uuid $FAST_MOUNT ext4 noatime 0 2"
    else
        printf 'UUID=%s\t%s\text4\tnoatime\t0\t2\n' "$_uuid" "$FAST_MOUNT" >> /etc/fstab
        echo "    appended UUID=$_uuid to /etc/fstab (noatime)"
    fi
fi

# --- 3. Layout for the IO-heavy trees ---
echo "[3/5] Directory layout ..."
TARGET_UID="$(id -u "$TARGET_USER")"
# the mount root itself: the migration probe and future agent-created
# top-level entries live here, so it belongs to the data owner too
_mount_owner="$(stat -c '%u' "$FAST_MOUNT")"
if [ "$_mount_owner" != "$TARGET_UID" ]; then
    run chown "$TARGET_USER:$TARGET_USER" "$FAST_MOUNT"
    echo "    $FAST_MOUNT -> owner $TARGET_USER"
fi
for d in containers models qemu caches; do
    run mkdir -p "$FAST_MOUNT/$d"
    _ostat=0
    _owner="$(stat -c '%u' "$FAST_MOUNT/$d" 2>&1)" || _ostat=$?
    if [ "$_ostat" -ne 0 ]; then
        _owner=0
    fi
    if [ "$_owner" != "$TARGET_UID" ]; then
        run chown "$TARGET_USER:$TARGET_USER" "$FAST_MOUNT/$d"
        echo "    $FAST_MOUNT/$d -> owner $TARGET_USER"
    else
        echo "    $FAST_MOUNT/$d already owned by $TARGET_USER"
    fi
done

# --- 4. Verify ---
echo "[4/5] Verify ..."
echo "    mount:   $(findmnt -no SOURCE,FSTYPE "$FAST_MOUNT" | tr '\n' ' ')"
echo "    label:   $(findmnt -no LABEL "$FAST_MOUNT")"
_probe="$FAST_MOUNT/.provision-probe"
if [ "$DRY_RUN" = true ]; then
    echo "    DRY-RUN: write+read+remove probe as $TARGET_USER at $_probe"
else
    runuser -u "$TARGET_USER" -- touch "$_probe"
    runuser -u "$TARGET_USER" -- test -w "$_probe"
    rm -f "$_probe"
    echo "    write probe as $TARGET_USER: ok"
fi

# --- 5. Swap relocation: unencrypted swap file on fast storage ---
# The old swap devices (/swap.img, /swap2.img) live inside the LUKS root,
# so every swapped page burns dm-crypt CPU on the shared write queue.
echo "[5/5] Swap relocation (${SWAP_FAST_GB}G unencrypted on $FAST_MOUNT) ..."
FAST_SWAP_DIR="$FAST_MOUNT/swap"
FAST_SWAP_FILE="$FAST_SWAP_DIR/swap0.img"
if grep -q "^${FAST_SWAP_FILE}[[:space:]]" /proc/swaps; then
    echo "    $FAST_SWAP_FILE already active - skipped"
else
    if [ ! -f "$FAST_SWAP_FILE" ]; then
        run mkdir -p "$FAST_SWAP_DIR"
        run fallocate -l "${SWAP_FAST_GB}G" "$FAST_SWAP_FILE"
    fi
    run chmod 0600 "$FAST_SWAP_FILE"
    run mkswap "$FAST_SWAP_FILE"
    run swapon "$FAST_SWAP_FILE"
    echo "    enabled $FAST_SWAP_FILE (${SWAP_FAST_GB}G)"
fi
if grep -q "^${FAST_SWAP_FILE}[[:space:]]" /etc/fstab; then
    echo "    fast swap already in /etc/fstab - skipped"
else
    if [ "$DRY_RUN" = true ]; then
        echo "    DRY-RUN: append to /etc/fstab: $FAST_SWAP_FILE none swap sw,nofail 0 0"
    else
        printf '%s\tnone\tswap\tsw,nofail\t0\t0\n' "$FAST_SWAP_FILE" >> /etc/fstab
        echo "    appended $FAST_SWAP_FILE to /etc/fstab (nofail)"
    fi
fi
for old_swap in /swap.img /swap2.img; do
    if [ ! -f "$old_swap" ]; then
        continue
    fi
    if grep -q "^${old_swap}[[:space:]]" /proc/swaps; then
        echo "    draining $old_swap (pages move to RAM/fast swap) ..."
        run swapoff "$old_swap"
    fi
    if grep -q "^${old_swap}[[:space:]]" /etc/fstab; then
        if [ "$DRY_RUN" = true ]; then
            echo "    DRY-RUN: comment out $old_swap in /etc/fstab"
            echo "    DRY-RUN: remove drained file $old_swap (reclaims its space)"
        else
            sed -i "s|^${old_swap}[[:space:]].*|# moved-to-fast-storage &|" /etc/fstab
            rm -f "$old_swap"
            echo "    $old_swap: fstab commented out, file removed"
        fi
    fi
done

# --- 6. Finite resources snapshot (limits we raised + live usage) ---
# Quick tracking view of the capacity raised by configure-multi-server-
# limits.sh plus the fast-storage swap, alongside current consumption.
echo "[6/6] Finite resources snapshot ..."
_echo_sysctls() {
    for key in "$@"; do
        _val=""
        _vrc=0
        _val="$(sysctl -n "$key")" || _vrc=$?
        if [ "$_vrc" -ne 0 ]; then
            _val="unreadable"
        fi
        printf '    %-52s %s\n' "$key" "$_val"
    done
}
echo "  inotify:"
_echo_sysctls fs.inotify.max_user_instances fs.inotify.max_user_watches \
    fs.inotify.max_queued_events
echo "  file descriptors:"
_echo_sysctls fs.nr_open fs.aio-max-nr
_runrc=0
_sys_nofile="$(systemctl show -p DefaultLimitNOFILE | cut -d= -f2)" || _runrc=$?
_usr_nofile="$(runuser -u "$TARGET_USER" -- systemctl --user show -p DefaultLimitNOFILE | cut -d= -f2)" || _runrc=$?
printf '    %-52s %s\n' "systemd DefaultLimitNOFILE (system)" "${_sys_nofile:-unreadable}"
printf '    %-52s %s\n' "systemd DefaultLimitNOFILE (user $TARGET_USER)" "${_usr_nofile:-unreadable}"
_fd_total=0
_fd_top=""
_fd_top_n=0
_pgreprc=0
_agent_pids="$(pgrep -u "$TARGET_USER" -x .)" || _pgreprc=$?
for _pid in $_agent_pids; do
    _nrc=0
    _n="$(ls "/proc/$_pid/fd" | wc -l)" || _nrc=$?
    if [ "$_nrc" -ne 0 ]; then
        _n=0
    fi
    _fd_total=$((_fd_total + _n))
    if [ "$_n" -gt "$_fd_top_n" ]; then
        _fd_top_n=$_n
        _fd_top="$(ps -o comm= -p "$_pid" 2>&1)" || _fd_top="pid-$_pid"
    fi
done
printf '    %-52s %s (%s open, top: %s with %s)\n' \
    "open fds of user $TARGET_USER" "sum across procs" "$_fd_total" "$_fd_top" "$_fd_top_n"
echo "  sockets / connection tracking:"
_echo_sysctls net.core.somaxconn net.core.netdev_max_backlog \
    net.ipv4.tcp_max_syn_backlog net.ipv4.ip_local_port_range \
    net.ipv4.tcp_max_tw_buckets net.ipv4.tcp_fin_timeout
_twrc=0
_tw_now="$(ss -H -o state time-wait | wc -l)" || _twrc=$?
if [ "$_twrc" -ne 0 ]; then
    _tw_now=0
fi
printf '    %-52s %s\n' "tcp time-wait sockets now" "$_tw_now"
_cnrc=0
_conn_count="$(cat /proc/sys/net/netfilter/nf_conntrack_count)" || _cnrc=$?
if [ "$_cnrc" -ne 0 ]; then
    _conn_count=0
fi
_cmrc=0
_conn_max="$(cat /proc/sys/net/netfilter/nf_conntrack_max)" || _cmrc=$?
if [ "$_cmrc" -ne 0 ]; then
    _conn_max=0
fi
printf '    %-52s %s / %s\n' "nf_conntrack entries used / max" "$_conn_count" "$_conn_max"
echo "  swap:"
_echo_sysctls vm.swappiness
free -h | grep -i '^swap' | sed 's/^/    /'
if [ -r /proc/swaps ]; then
    grep -v '^Filename' /proc/swaps | while read -r _swdev _swtype _swsize _swused _swprio; do
        printf '    %-52s used %s kB of %s kB (prio %s)\n' "$_swdev" "$_swused" "$_swsize" "$_swprio"
    done
fi

echo ""
echo "=== Done ==="
echo "Fast storage ready at $FAST_MOUNT (persistent via /etc/fstab)."
echo "Next: as the agent user, run the data migration:"
echo "    make migrate-fast-storage                # plan (dry-run by default is NOT set; use --dry-run first)"
echo "    bash scripts/setup/migrate-fast-storage.sh --dry-run"
echo "    bash scripts/setup/migrate-fast-storage.sh"
