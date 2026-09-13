#!/bin/bash
set -euo pipefail

# hang-evidence-sampler.sh
#
# Persistent lightweight sampler for freeze/hang post-mortems. The 2026-09
# incidents left no live evidence (operator power-cycles the box), so this
# records kernel-visible truth continuously to the FAST disk, which survives
# restarts:
#
#   psi.log      - /proc/pressure io/cpu/memory (some+full, avg10/60/300)
#   load.log     - loadavg + runnable tasks + blocked (D-state) count
#   mem.log      - MemAvailable/SwapFree/Dirty/Writeback
#   disk.log     - absolute /proc/diskstats counters for root+fast devices
#                  (analysis computes deltas: io_ticks delta = busy ms)
#   kern.log     - any new hang-class kernel lines (hung_task, blocked-for,
#                  OOM, I/O error, i915 atomic update failure, GPU reset)
#
# Intentionally agent-owned user units: /proc/* and journalctl -k are
# readable from uid 1000 (adm group). Runs forever; systemd restarts it.
#
# Usage:
#   hang-evidence-sampler.sh [interval-seconds]   (default 10)
#
# Install (user):  make install-diagnostics
#                  (unit hang-evidence-sampler.service, enabled + started)

INTERVAL="${1:-10}"
OUT_DIR="${HANG_DIAG_DIR:-/mnt/ws-fast/diag}"
mkdir -p "$OUT_DIR"

# Devices to track: dm/NVMe pair carrying root and fast storage.
DEVS="nvme0n1 nvme1n1 nvme1n1p1 dm-0"

_last_kmsg_ts=0

while :; do
    _ts="$(date -Is)"
    _epoch="$(date +%s)"

    # --- PSI ---
    {
        printf '%s' "$_ts"
        for _f in io cpu memory; do
            _s=""
            _frc=0
            _s="$(grep '^some' "/proc/pressure/$_f" | grep -oE 'avg[0-9]+=[0-9.]+' | tr '\n' ' ')" || _frc=$?
            _u=""
            _urc=0
            _u="$(grep '^full' "/proc/pressure/$_f" | grep -oE 'avg[0-9]+=[0-9.]+' | tr '\n' ' ')" || _urc=$?
            printf ' %s_some=[%s] %s_full=[%s]' "$_f" "${_s:-NA}" "$_f" "${_u:-NA}"
        done
        printf '\n'
    } >> "$OUT_DIR/psi.log"

    # --- load + D-state count ---
    _runq="$(cut -d' ' -f1-5 /proc/loadavg)"
    _dblocked=0
    _drc=0
    _dblocked="$(ps -eo stat --no-headers | grep -c '^D')" || _drc=$?
    if [ "$_drc" -ne 0 ]; then
        _dblocked=0
    fi
    printf '%s load=[%s] dstate=%s\n' "$_ts" "$_runq" "$_dblocked" >> "$OUT_DIR/load.log"

    # --- memory ---
    _mi="$(grep -E '^(MemAvailable|SwapFree|Dirty|Writeback):' /proc/meminfo | tr '\n' ' ')"
    printf '%s %s\n' "$_ts" "$_mi" >> "$OUT_DIR/mem.log"

    # --- diskstats (absolute counters; analysis deltas them) ---
    {
        printf '%s' "$_ts"
        for _d in $DEVS; do
            _line=""
            _lrc=0
            _line="$(grep -E " ${_d} " /proc/diskstats | tr -s ' ')" || _lrc=$?
            if [ "$_lrc" -ne 0 ] || [ -z "$_line" ]; then
                printf ' %s=absent' "$_d"
            else
                # fields (after tr): 4=reads 8=writes 10=io_ticks_ms
                _reads="$(printf '%s\n' "$_line" | sed -n '1p' | awk '{print $4}')"
                _writes="$(printf '%s\n' "$_line" | sed -n '1p' | awk '{print $8}')"
                _ticks="$(printf '%s\n' "$_line" | sed -n '1p' | awk '{print $10}')"
                printf ' %s=r:%s w:%s ms:%s' "$_d" "${_reads:-?}" "${_writes:-?}" "${_ticks:-?}"
            fi
        done
        printf '\n'
    } >> "$OUT_DIR/disk.log"

    # --- hang-class kernel lines since last sample ---
    if [ "$_last_kmsg_ts" -gt 0 ]; then
        _kraw=""
        _krc=0
        _kraw="$(journalctl -k --since "@$_last_kmsg_ts" --no-pager -o short)" || _krc=$?
        if [ "$_krc" -eq 0 ] && [ -n "$_kraw" ]; then
            _kout=""
            _grc=0
            _kout="$(printf '%s\n' "$_kraw" | grep -E 'hung_task|blocked for more than|Out of memory|I/O error|Atomic update failure|GPU HANG|drm.*ERROR|nvme.*timeout')" || _grc=$?
            if [ "$_grc" -eq 0 ] && [ -n "$_kout" ]; then
                printf '%s\n%s\n' "$_ts" "$_kout" >> "$OUT_DIR/kern.log"
            fi
        fi
    fi
    _last_kmsg_ts=$_epoch

    sleep "$INTERVAL"
done
