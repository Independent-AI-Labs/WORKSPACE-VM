#!/bin/bash
set -euo pipefail

# Updates the Intel DG2 userspace driver stack and upstream Arc firmware.
# Usage: sudo bash scripts/setup/update-intel-dg2-drivers.sh [YYYYMMDD]

RELEASE="${1:-20260810}"
BASE_URL="https://cdn.kernel.org/pub/linux/kernel/firmware"
ARCHIVE="linux-firmware-${RELEASE}.tar.xz"
CHECKSUMS="sha256sums.asc"
FIRMWARE=(dg2_dmc_ver2_08.bin dg2_guc_70.bin dg2_huc_gsc.bin)

if [ "$(id -u)" -ne 0 ]; then
    printf 'error: run as root (sudo bash %s)\n' "$0" >&2
    exit 1
fi

if ! [[ "$RELEASE" =~ ^[0-9]{8}$ ]]; then
    printf 'error: firmware release must be YYYYMMDD, got %s\n' "$RELEASE" >&2
    exit 1
fi

workdir="$(mktemp -d)"
backup_dir="/var/backups/intel-dg2-firmware/$RELEASE"
trap 'rm -rf "$workdir"' EXIT

apt-get update
apt-get install -y linux-firmware mesa-vulkan-drivers libgl1-mesa-dri libze-intel-gpu1 intel-media-va-driver-non-free
curl --fail --location --remote-name --output-dir "$workdir" "$BASE_URL/$ARCHIVE"
curl --fail --location --remote-name --output-dir "$workdir" "$BASE_URL/$CHECKSUMS"
(cd "$workdir" && grep " $ARCHIVE$" "$CHECKSUMS" | sha256sum --check --status -)

for firmware in "${FIRMWARE[@]}"; do
    tar --extract --to-stdout --file "$workdir/$ARCHIVE" \
        "linux-firmware-$RELEASE/i915/$firmware" > "$workdir/$firmware"
done

install --directory --mode 0755 /lib/firmware/i915
install --directory --mode 0755 "$backup_dir"
for firmware in "${FIRMWARE[@]}"; do
    if [ -e "/lib/firmware/i915/$firmware" ]; then
        cp --archive "/lib/firmware/i915/$firmware" "$backup_dir/$firmware"
    fi
    install --mode 0644 "$workdir/$firmware" "/lib/firmware/i915/$firmware"
done

update-initramfs -u -k all
printf 'Installed DG2 firmware from %s. Reboot to load it.\n' "$ARCHIVE"
