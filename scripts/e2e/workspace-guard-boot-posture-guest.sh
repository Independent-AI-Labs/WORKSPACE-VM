#!/usr/bin/env bash
# Rehearse the boot-posture kernel cmdline inside a disposable QEMU guest.
#
# The host edit that activates the bpf LSM and lockdown=integrity is the same
# transformation this script applies to the guest's own grub: read the active
# LSM list, append bpf, add lockdown=integrity, regenerate grub. Running it in
# a guest proves the edit boots before it is applied to the operator's host.
#
# Modes:
#   apply   edit /etc/default/grub and regenerate the grub config
#   verify  assert the running guest activated the bpf LSM and lockdown
#
# Mutates the guest only. Requires root inside the guest.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: boot-posture guest script requires root in the guest" >&2
    exit 1
fi

readonly GRUB_FILE=/etc/default/grub
readonly GRUB_KEY='GRUB_CMDLINE_LINUX='

lsm_list() {
    if [[ -r /sys/kernel/security/lsm ]]; then
        cat /sys/kernel/security/lsm
    else
        printf 'landlock,lockdown,yama,integrity,apparmor'
    fi
}

grub_cmdline() {
    local line value
    value=''
    while IFS= read -r line; do
        case "$line" in
            "${GRUB_KEY}"*)
                value="${line#"${GRUB_KEY}"}"
                value="${value%\"}"
                value="${value#\"}"
                ;;
        esac
    done < "$GRUB_FILE"
    printf '%s' "$value"
}

apply() {
    if [[ ! -f "$GRUB_FILE" ]]; then
        echo "ERROR: $GRUB_FILE is missing; the guest does not use grub" >&2
        exit 1
    fi

    local lsm current filtered new line
    lsm="$(lsm_list)"
    case ",$lsm," in
        *,bpf,*) ;;
        *) lsm="$lsm,bpf" ;;
    esac

    current="$(grub_cmdline)"
    filtered=''
    for token in $current; do
        case "$token" in
            lsm=*|lockdown=*) continue ;;
        esac
        filtered="$filtered $token"
    done
    new="${filtered# }"
    if [[ -n "$new" ]]; then
        new="$new "
    fi
    new="${new}lsm=$lsm lockdown=integrity"

    cp -a "$GRUB_FILE" "$GRUB_FILE.boot-posture.bak"
    : > "$GRUB_FILE.boot-posture.new"
    while IFS= read -r line; do
        case "$line" in
            "${GRUB_KEY}"*)
                printf '%s\n' "${GRUB_KEY}\"$new\"" >> "$GRUB_FILE.boot-posture.new"
                ;;
            *)
                printf '%s\n' "$line" >> "$GRUB_FILE.boot-posture.new"
                ;;
        esac
    done < "$GRUB_FILE"
    chown --reference="$GRUB_FILE" "$GRUB_FILE.boot-posture.new"
    chmod --reference="$GRUB_FILE" "$GRUB_FILE.boot-posture.new"
    mv "$GRUB_FILE.boot-posture.new" "$GRUB_FILE"

    update-grub
    echo "APPLY: grub updated"
    echo "APPLY: new cmdline $(grub_cmdline)"
}

verify() {
    local fail cmdline lsm lockdown uptime_secs
    fail=0

    cmdline="$(cat /proc/cmdline)"
    echo "VERIFY: cmdline $cmdline"

    lsm="$(cat /sys/kernel/security/lsm)"
    echo "VERIFY: lsm $lsm"
    case ",$lsm," in
        *,bpf,*) echo "VERIFY: bpf LSM active" ;;
        *)
            echo "VERIFY-FAIL: bpf is not in the active LSM list" >&2
            fail=1
            ;;
    esac

    if [[ -r /sys/kernel/security/lockdown ]]; then
        lockdown="$(cat /sys/kernel/security/lockdown)"
        echo "VERIFY: lockdown $lockdown"
        case "$lockdown" in
            *'[integrity]'*) echo "VERIFY: lockdown integrity active" ;;
            *)
                echo "VERIFY-FAIL: lockdown is not in integrity mode" >&2
                fail=1
                ;;
        esac
    else
        echo "VERIFY-FAIL: /sys/kernel/security/lockdown is unavailable" >&2
        fail=1
    fi

    case " $cmdline " in
        *' lsm='*) ;;
        *)
            echo "VERIFY-FAIL: lsm= is absent from the boot cmdline" >&2
            fail=1
            ;;
    esac
    case " $cmdline " in
        *' lockdown=integrity'*) ;;
        *)
            echo "VERIFY-FAIL: lockdown=integrity is absent from the cmdline" >&2
            fail=1
            ;;
    esac

    uptime_secs="$(cut -d. -f1 /proc/uptime)"
    echo "VERIFY: uptime ${uptime_secs}s"
    if [[ "$fail" -ne 0 ]]; then
        echo "BOOT-POSTURE: FAIL"
        exit 1
    fi
    echo "BOOT-POSTURE: PASS"
}

case "${1:-}" in
    apply) apply ;;
    verify) verify ;;
    *)
        echo "usage: $0 apply|verify" >&2
        exit 2
        ;;
esac
