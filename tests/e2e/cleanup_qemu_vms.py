"""Remove orphaned QEMU E2E VM directories."""

from __future__ import annotations

from tests.e2e.qemu_cleanup import cleanup_orphan_qemu_vms


def main() -> int:
    removed = cleanup_orphan_qemu_vms(max_age_seconds=0)
    if removed:
        print(f"Removed {len(removed)} QEMU VM dir(s)")
    else:
        print("No QEMU VM dirs to remove")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
