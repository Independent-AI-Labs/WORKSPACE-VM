#!/bin/bash
set -euo pipefail

# Builds and installs an upstream stable Linux 7.1.x kernel as Debian packages.
# Usage: sudo bash scripts/setup/install-linux-7.1.sh [7.1.x]

VERSION="${1:-7.1.8}"
BASE_URL="https://cdn.kernel.org/pub/linux/kernel/v7.x"
ARCHIVE="linux-$VERSION.tar.xz"
CHECKSUMS="sha256sums.asc"

if [ "$(id -u)" -ne 0 ]; then
    printf 'error: run as root (sudo bash %s)\n' "$0" >&2
    exit 1
fi

if ! [[ "$VERSION" =~ ^7\.1\.[0-9]+$ ]]; then
    printf 'error: kernel version must be stable 7.1.x, got %s\n' "$VERSION" >&2
    exit 1
fi

if mokutil_path="$(command -v mokutil)"; then
    secure_boot_state="$("$mokutil_path" --sb-state)"
    if [[ "$secure_boot_state" == *'SecureBoot enabled'* ]]; then
        printf 'error: Secure Boot is enabled; this locally built kernel is unsigned.\n' >&2
        exit 1
    fi
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

apt-get update
apt-get install -y build-essential bc bison debhelper flex libdw-dev libelf-dev libncurses-dev libssl-dev dwarves rsync
curl --fail --location --remote-name --output-dir "$workdir" "$BASE_URL/$ARCHIVE"
curl --fail --location --remote-name --output-dir "$workdir" "$BASE_URL/$CHECKSUMS"
(cd "$workdir" && grep " $ARCHIVE$" "$CHECKSUMS" | sha256sum --check --status -)

tar --extract --file "$workdir/$ARCHIVE" --directory "$workdir"
source_dir="$workdir/linux-$VERSION"
cp "/boot/config-$(uname -r)" "$source_dir/.config"
(cd "$source_dir" && make olddefconfig)
perl -pi -e 's/debhelper-compat \(= 12\)/debhelper-compat (= 13)/' "$source_dir/debian/control"
(cd "$source_dir" && make -j"${KERNEL_BUILD_JOBS:-8}" bindeb-pkg)

apt-get install -y "$workdir"/*.deb
printf 'Installed Linux %s. Reboot to test it; the current kernel remains available in GRUB.\n' "$VERSION"
