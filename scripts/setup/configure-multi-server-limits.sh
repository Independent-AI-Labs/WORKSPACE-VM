#!/bin/bash
set -euo pipefail

# configure-multi-server-limits.sh
#
# Raises kernel + systemd limits so this host can run many concurrent
# dev servers, containers, and later hundreds of thousands of transient
# (proxy-style) connections. The stock Ubuntu defaults caused two live
# incidents on 2026-09-11:
#   - conmon: "Failed to create inotify fd"  (fs.inotify.max_user_instances=128)
#   - zk-portal-dev Turbopack crash loop "Too many open files (os error 24)"
#     (systemd DefaultLimitNOFILE soft limit 1024)
# while a GUARD pre-push podman run + ansible provisioning landed on top.
#
# Persistent config written by this script:
#   /etc/sysctl.d/70-workspace-multi-server.conf          (kernel limits, applied at boot)
#   /etc/modprobe.d/nf_conntrack-workspace.conf           (conntrack hash size)
#   /etc/systemd/system.conf.d/50-workspace-multi-server.conf  (system manager fd limits)
#   /etc/systemd/user.conf.d/50-workspace-multi-server.conf    (user manager fd limits)
#   /swap2.img + /etc/fstab swap entry                    (total swap raised to 32G)
# Plus immediate relief: chmod 0755 on the root-only-installed podman
# user generator (deploy-ci installs it 0700; a *user* generator must be
# user-executable - tracked separately in WORKSPACE-CI deploy-ci).
#
# Idempotent: safe to re-run; overwrites the files above with these values.
# Usage: sudo bash scripts/setup/configure-multi-server-limits.sh
#    or: sudo make enforce-multi-server-limits

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script requires root. Run with: sudo bash $0" >&2
    exit 1
fi

TARGET_USER="${SUDO_USER:-agent}"
TARGET_UID="$(id -u "$TARGET_USER")"

SYSCTL_FILE="/etc/sysctl.d/70-workspace-multi-server.conf"
MODPROBE_FILE="/etc/modprobe.d/nf_conntrack-workspace.conf"
SYSTEM_CONF_DIR="/etc/systemd/system.conf.d"
USER_CONF_DIR="/etc/systemd/user.conf.d"
SYSTEM_LIMITS_FILE="$SYSTEM_CONF_DIR/50-workspace-multi-server.conf"
USER_LIMITS_FILE="$USER_CONF_DIR/50-workspace-multi-server.conf"
PODMAN_GENERATOR="/usr/local/lib/systemd/user-generators/podman-user-generator"
NOFILE_LIMIT="1048576"
SWAP_TARGET_GB=32
# mkswap reserves a metadata page per swap device and SwapTotal rounds
# down; a 64M slack makes the target check exact-enough instead of
# off-by-one-page (8G + 24G reads back as 32767M)
SWAP_SLACK_KB=65536
SWAP_FILE="/swap2.img"

echo "=== Enforcing multi-server capacity limits ==="
echo ""

# --- 1. Kernel sysctls (persistent via sysctl.d, applied now) ---
echo "[1/6] Writing $SYSCTL_FILE ..."
mkdir -p /etc/sysctl.d
cat > "$SYSCTL_FILE" << 'SYSCTL_EOF'
# WORKSPACE multi-server capacity limits (2026-09-11 incident follow-up).
# Sized for: multiple Next.js/Turbopack dev servers + podman containers +
# hundreds of thousands of transient proxy connections.

# --- file/inotify: watchers for dev servers, containers, build tools ---
fs.inotify.max_user_instances = 1024
fs.inotify.max_user_watches = 1048576
fs.inotify.max_queued_events = 65536
fs.aio-max-nr = 1048576
# per-process fd ceiling so LimitNOFILE=1048576 is legal
fs.nr_open = 2097152

# --- listen + accept queues ---
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 16384
net.ipv4.tcp_max_syn_backlog = 65536

# --- transient connection recycling ---
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_max_tw_buckets = 1048576
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_tw_reuse = 1

# --- socket buffers for high-throughput proxying ---
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# --- conntrack: podman/nftables NAT'd flows (1M entries ~ 320MB kernel mem;
# add RAM if this becomes the bottleneck) ---
net.netfilter.nf_conntrack_max = 1048576
net.netfilter.nf_conntrack_tcp_timeout_established = 86400

# --- swap thrash mitigation (94G RAM / 8G swap host) ---
vm.swappiness = 10
SYSCTL_EOF
chmod 644 "$SYSCTL_FILE"
echo "    written"

# --- 2. Apply sysctls now, verify each key ---
echo "[2/6] Applying kernel limits ..."
FAILURES=0
MISSING=0
while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    key="${key// /}"
    value="${line#*=}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [ ! -e "/proc/sys/${key//./\/}" ]; then
        echo "    WARN  $key not present on this kernel (module not loaded?) - skipped" >&2
        MISSING=$((MISSING + 1))
        continue
    fi
    _st=0
    _out="$(sysctl -w "$key=$value" 2>&1)" || _st=$?
    if [ "$_st" -ne 0 ]; then
        echo "    FAIL  $key=$value: $_out" >&2
        FAILURES=$((FAILURES + 1))
        continue
    fi
    # sysctl read-back renders multi-value keys with tabs and ends with a
    # newline; squeeze all whitespace runs to single spaces, then trim the
    # edges (tr turns the trailing newline into a trailing space)
    actual="$(sysctl -n "$key" | tr -s '[:space:]' ' ')"
    actual="${actual# }"
    actual="${actual% }"
    expected="$(printf '%s' "$value" | tr -s '[:space:]' ' ')"
    expected="${expected# }"
    expected="${expected% }"
    if [ "$actual" != "$expected" ]; then
        echo "    FAIL  $key expected [$expected] read back [$actual]" >&2
        FAILURES=$((FAILURES + 1))
        continue
    fi
    echo "    ok    $key = $value"
done < "$SYSCTL_FILE"

# --- 3. conntrack hash size (module param, not a sysctl) ---
echo "[3/6] Conntrack hash size ..."
echo "options nf_conntrack hashsize=262144" > "$MODPROBE_FILE"
chmod 644 "$MODPROBE_FILE"
HASH_PARAM="/sys/module/nf_conntrack/parameters/hashsize"
if [ -w "$HASH_PARAM" ]; then
    echo 262144 > "$HASH_PARAM"
    echo "    runtime hashsize=262144 (persistent via $MODPROBE_FILE)"
else
    echo "    $HASH_PARAM not writable or module not loaded - applied at next module load via $MODPROBE_FILE" >&2
fi

# --- 4. systemd DefaultLimitNOFILE (system + user managers) ---
echo "[4/6] systemd fd limits (DefaultLimitNOFILE=$NOFILE_LIMIT) ..."
mkdir -p "$SYSTEM_CONF_DIR" "$USER_CONF_DIR"
printf '[Manager]\nDefaultLimitNOFILE=%s\n' "$NOFILE_LIMIT" > "$SYSTEM_LIMITS_FILE"
printf '[Manager]\nDefaultLimitNOFILE=%s\n' "$NOFILE_LIMIT" > "$USER_LIMITS_FILE"
chmod 644 "$SYSTEM_LIMITS_FILE" "$USER_LIMITS_FILE"
systemctl daemon-reexec
echo "    system manager re-executed"
runuser -u "$TARGET_USER" -- env XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    systemctl --user daemon-reexec
echo "    user manager (uid=$TARGET_UID) re-executed"
echo "    NOTE: already-running services keep old soft limits until restarted."

# --- 5. Immediate relief: user-executable podman generator ---
echo "[5/6] podman user generator mode ..."
if [ -e "$PODMAN_GENERATOR" ]; then
    _mode="$(stat -c '%a' "$PODMAN_GENERATOR")"
    if [ "$_mode" != "755" ]; then
        chmod 0755 "$PODMAN_GENERATOR"
        echo "    $PODMAN_GENERATOR: $_mode -> 755 (user generators must be user-executable)"
        echo "    deploy-ci still installs it 0700 - fix belongs in WORKSPACE-CI deploy-ci"
    else
        echo "    already 755"
    fi
else
    echo "    $PODMAN_GENERATOR not present - skipped" >&2
fi

# --- 6. Total swap raised to target (adds a second swapfile; never touches
#        the existing in-use one - growing it would require swapoff under
#        load) ---
echo "[6/6] Total swap target: ${SWAP_TARGET_GB}G ..."
SWAP_TOTAL_KB="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
SWAP_TARGET_KB=$((SWAP_TARGET_GB * 1024 * 1024))
SWAP_FLOOR_KB=$((SWAP_TARGET_KB - SWAP_SLACK_KB))
SWAP_FAILURES=0
if [ "$SWAP_TOTAL_KB" -ge "$SWAP_FLOOR_KB" ]; then
    echo "    total swap already $((SWAP_TOTAL_KB / 1024))M >= ${SWAP_TARGET_GB}G - skipped"
else
    DEFICIT_MB=$(((SWAP_TARGET_KB - SWAP_TOTAL_KB) / 1024))
    if grep -q "^${SWAP_FILE}[[:space:]]" /proc/swaps; then
        echo "    FAIL  $SWAP_FILE is active but total swap is still below target" >&2
        SWAP_FAILURES=$((SWAP_FAILURES + 1))
    else
        if [ ! -e "$SWAP_FILE" ]; then
            _st=0
            fallocate -l "${DEFICIT_MB}M" "$SWAP_FILE" || _st=$?
            if [ "$_st" -ne 0 ]; then
                echo "    fallocate failed (status=$_st) - writing with dd instead" >&2
                dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$DEFICIT_MB" status=progress
            fi
        fi
        chmod 0600 "$SWAP_FILE"
        mkswap "$SWAP_FILE"
        swapon "$SWAP_FILE"
        if ! grep -q "^${SWAP_FILE}[[:space:]]" /etc/fstab; then
            printf '%s\tnone\tswap\tsw\t0\t0\n' "$SWAP_FILE" >> /etc/fstab
            echo "    appended $SWAP_FILE to /etc/fstab"
        else
            echo "    $SWAP_FILE already in /etc/fstab"
        fi
        echo "    enabled $SWAP_FILE (deficit was ${DEFICIT_MB}M)"
    fi
    SWAP_TOTAL_KB="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
    if [ "$SWAP_TOTAL_KB" -lt "$SWAP_FLOOR_KB" ]; then
        echo "    FAIL  total swap is $((SWAP_TOTAL_KB / 1024))M, below ${SWAP_TARGET_GB}G target" >&2
        SWAP_FAILURES=$((SWAP_FAILURES + 1))
    else
        echo "    ok    total swap now $((SWAP_TOTAL_KB / 1024))M"
    fi
fi

echo ""
echo "=== Restart dev servers to pick up new fd limits ==="
for unit in zk-portal-dev.service workspace-portal-dev.service; do
    _active=0
    _active_out="$(runuser -u "$TARGET_USER" -- env XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        systemctl --user is-active "$unit" 2>&1)" || _active=$?
    if [ "$_active" -eq 0 ]; then
        runuser -u "$TARGET_USER" -- env XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
            systemctl --user restart "$unit"
        echo "    restarted $unit"
    else
        echo "    $unit not active - skipped"
    fi
done

echo ""
echo "=== Done ==="
echo "Capacity limits in place (persistent across reboots):"
echo "  - inotify: 1024 instances / 1048576 watches per user"
echo "  - sockets: somaxconn=65535, syn_backlog=65536, port range 1024-65535"
echo "  - transient: tw_buckets=1048576, fin_timeout=30s, tw_reuse=1"
echo "  - conntrack: 1048576 entries, hashsize=262144, established timeout 1d"
echo "  - per-process fds: DefaultLimitNOFILE=1048576 (system + user managers)"
echo "  - total swap: ${SWAP_TARGET_GB}G target (/swap2.img + /etc/fstab entry)"
echo "  - vm.swappiness=10"
if [ "$SWAP_FAILURES" -gt 0 ]; then
    echo "ERROR: swap extension failed (see above)" >&2
    exit 1
fi
if [ "$MISSING" -gt 0 ]; then
    echo "WARN: $MISSING sysctl key(s) not present on this kernel (see above)" >&2
fi
if [ "$FAILURES" -gt 0 ]; then
    echo "ERROR: $FAILURES sysctl setting(s) failed to apply or verify" >&2
    exit 1
fi
echo "OK: all applicable kernel limits applied and verified"
