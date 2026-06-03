"""ami storage: aggregated disk-usage report.

Composes existing utilities:
- ami.scripts.utils.sys_info: ProgressBar + get_size_str (root filesystem usage)
- ami.scripts.utils.analyze_disk_usage: du-based top-25 directory breakdown
- ami.cli_components.status_containers.get_container_sizes: podman volume sizes
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import psutil

from ami.cli.status_containers import get_container_sizes
from ami.scripts.utils.analyze_disk_usage import analyze
from ami.scripts.utils.sys_info import ProgressBar, get_size_str

_BAR_WIDTH = 40


def _print_root_disk() -> None:
    disk = psutil.disk_usage(".")
    bar = ProgressBar(width=_BAR_WIDTH)
    line = bar.render(
        percent=disk.percent,
        label="Root Disk",
        value=f"{get_size_str(disk.used)} / {get_size_str(disk.total)}",
    )
    print(line)


def _clean_uv_cache() -> None:
    print("  * uv cache...", end=" ", flush=True)
    r = subprocess.run(
        ["uv", "cache", "clean", "--force"],
        capture_output=True,
        text=True,
        check=False,
    )
    print("done" if r.returncode == 0 else f"skipped ({r.stderr.strip()})")


def _clean_podman_dangling() -> None:
    print("  * dangling podman images...", end=" ", flush=True)
    r = subprocess.run(
        ["podman", "image", "prune", "-f"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode == 0:
        count = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        print(f"done ({count} removed)" if count else "none to remove")
    else:
        print(f"skipped ({r.stderr.strip()})")


def _clean_project_tmp(project_path: str) -> None:
    proj_tmp = Path(project_path).expanduser() / "tmp"
    if not proj_tmp.exists():
        print(f"  * {proj_tmp}... skipped (not found)")
        return
    print(f"  * {proj_tmp}...", end=" ", flush=True)
    count = 0
    try:
        for item in list(proj_tmp.iterdir()):
            if item.name == ".gitkeep":
                continue
            count += 1 if _remove_path(item) else 0
        print("done" if count else "empty")
    except Exception as e:
        print(f"error: {e}")


def _remove_path(item: Path) -> bool:
    try:
        if item.is_dir():
            subprocess.run(
                ["rm", "-rf", str(item)],
                capture_output=True,
                check=False,
            )
        else:
            item.unlink(missing_ok=True)
    except Exception:
        return False
    else:
        return True


def _clean_system_tmp() -> None:
    print("  * /tmp...", end=" ", flush=True)
    try:
        cleaned = sum(1 for item in Path("/tmp").iterdir() if _remove_path(item))
        print(f"done ({cleaned} items removed)")
    except Exception as e:
        print(f"error: {e}")


def _run_clean(project_path: str) -> None:
    """Prune safe caches and temp directories."""
    print("\n--- Cleaning safe caches ---")
    _clean_uv_cache()
    _clean_podman_dangling()
    _clean_project_tmp(project_path)
    _clean_system_tmp()


def _print_container_sizes() -> None:
    sizes = get_container_sizes()
    print("\nContainer Sizes")
    print("-" * 60)
    if not sizes:
        print("  No containers (podman unavailable or none running).")
        return
    for s in sizes:
        name = s["name"]
        writable = s["writable"]
        virtual = s["virtual"]
        print(f"  {name:<32} writable={writable:<10} virtual={virtual}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="storage",
        description=(
            "Aggregated storage report: root disk, repo breakdown, container sizes."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to break down (default: current directory)",
    )
    parser.add_argument(
        "--no-containers",
        action="store_true",
        help="Skip container size collection",
    )
    parser.add_argument(
        "--no-breakdown",
        action="store_true",
        help="Skip top-25 directory breakdown",
    )
    parser.add_argument(
        "--no-fs-scan",
        action="store_true",
        help="Skip root filesystem scan",
    )
    parser.add_argument(
        "--no-tmp-scan",
        action="store_true",
        help="Skip /tmp breakdown",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Prune safe caches: uv cache, podman dangling images, ./tmp/, /tmp/",
    )
    args = parser.parse_args()
    if args.clean:
        _run_clean(args.path)
    _print_root_disk()
    if not args.no_breakdown:
        print()
        analyze(args.path)
    if not args.no_fs_scan:
        print()
        print("--- Other directories on this filesystem ---")
        analyze("/", same_fs=True)
    if not args.no_tmp_scan:
        print()
        print("--- /tmp breakdown ---")
        analyze("/tmp")
    if not args.no_containers:
        _print_container_sizes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
