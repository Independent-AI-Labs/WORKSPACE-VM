"""Probe discrete Vulkan GPUs and prefer headless devices (zero connected monitors)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class VulkanGpu(NamedTuple):
    index: int
    free_bytes: int
    budget_bytes: int
    usage_bytes: int
    device_name: str
    pci_slot: str
    monitor_count: int


def pci_slot_from_parts(domain: int, bus: int, device: int, function: int) -> str:
    return f"{domain:04x}:{bus:02x}:{device:02x}.{function}"


def drm_monitor_counts(drm_root: Path = Path("/sys/class/drm")) -> dict[str, int]:
    """Map PCI_SLOT_NAME to count of connected DRM connectors."""
    counts: dict[str, int] = {}
    if not drm_root.is_dir():
        return counts

    for card in sorted(drm_root.glob("card[0-9]")):
        if not card.is_dir() or card.name.endswith(("-HDMI-A", "-DP", "-DVI-I")):
            continue
        uevent = card / "device" / "uevent"
        pci_slot = ""
        if uevent.is_file():
            for line in uevent.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                if line.startswith("PCI_SLOT_NAME="):
                    pci_slot = line.split("=", 1)[1].strip()
                    break
        if not pci_slot:
            continue
        connected = 0
        for status_path in card.glob(f"{card.name}-*/status"):
            state = status_path.read_text(encoding="utf-8", errors="replace").strip()
            if state == "connected":
                connected += 1
        counts[pci_slot] = connected
    return counts


def parse_vulkan_discrete_gpus(
    text: str,
    monitor_counts: dict[str, int] | None = None,
) -> list[VulkanGpu]:
    """Parse vulkaninfo text for discrete GPUs with memory and monitor counts."""
    monitors = monitor_counts if monitor_counts is not None else drm_monitor_counts()
    parts = re.split(r"^GPU(\d+):\s*$", text, flags=re.MULTILINE)
    gpus: list[VulkanGpu] = []

    for i in range(1, len(parts), 2):
        idx = int(parts[i])
        body = parts[i + 1]
        if "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU" not in body:
            continue

        name_m = re.search(r"deviceName\s*=\s*(.+)", body)
        device_name = name_m.group(1).strip() if name_m else f"GPU{idx}"

        domain_m = re.search(r"pciDomain\s*=\s*(\d+)", body)
        bus_m = re.search(r"pciBus\s*=\s*(\d+)", body)
        dev_m = re.search(r"pciDevice\s*=\s*(\d+)", body)
        fn_m = re.search(r"pciFunction\s*=\s*(\d+)", body)
        pci_slot = ""
        monitor_count = 0
        if domain_m and bus_m and dev_m and fn_m:
            pci_slot = pci_slot_from_parts(
                int(domain_m.group(1)),
                int(bus_m.group(1)),
                int(dev_m.group(1)),
                int(fn_m.group(1)),
            )
            monitor_count = monitors.get(pci_slot, 0)

        heap_blocks = re.split(r"^\s*memoryHeaps\[\d+\]:\s*$", body, flags=re.MULTILINE)
        budget = None
        usage = None
        for block in heap_blocks[1:]:
            if "MEMORY_HEAP_DEVICE_LOCAL_BIT" not in block:
                continue
            budget_m = re.search(r"budget\s*=\s*(\d+)", block)
            usage_m = re.search(r"usage\s*=\s*(\d+)", block)
            if budget_m and usage_m:
                budget = int(budget_m.group(1))
                usage = int(usage_m.group(1))
                break
        if budget is None or usage is None:
            continue

        free = max(budget - usage, 0)
        gpus.append(
            VulkanGpu(
                index=idx,
                free_bytes=free,
                budget_bytes=budget,
                usage_bytes=usage,
                device_name=device_name,
                pci_slot=pci_slot,
                monitor_count=monitor_count,
            )
        )
    return gpus


def select_best_gpu(gpus: list[VulkanGpu]) -> VulkanGpu | None:
    """Prefer zero-monitor GPUs; break ties by most free device-local memory."""
    if not gpus:
        return None
    headless = [gpu for gpu in gpus if gpu.monitor_count == 0]
    pool = headless or gpus
    return max(pool, key=lambda gpu: gpu.free_bytes)


def run_vulkaninfo() -> str:
    try:
        result = subprocess.run(
            ["vulkaninfo"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = f"vulkaninfo failed (exit {exc.returncode})"
        raise RuntimeError(msg) from exc
    return result.stdout


def probe_vulkan_gpus() -> list[VulkanGpu]:
    return parse_vulkan_discrete_gpus(run_vulkaninfo())


def format_shell_records(gpus: list[VulkanGpu]) -> str:
    lines: list[str] = []
    for gpu in gpus:
        lines.append(f"GPU_INDEX={gpu.index}")
        lines.append(f"FREE_BYTES={gpu.free_bytes}")
        lines.append(f"BUDGET_BYTES={gpu.budget_bytes}")
        lines.append(f"USAGE_BYTES={gpu.usage_bytes}")
        lines.append(f"DEVICE_NAME={gpu.device_name}")
        lines.append(f"PCI_SLOT={gpu.pci_slot}")
        lines.append(f"MONITOR_COUNT={gpu.monitor_count}")
        lines.append("---")
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print("usage: vulkan_gpu_probe.py [--select-best]")
        return 0

    try:
        gpus = probe_vulkan_gpus()
    except (OSError, RuntimeError):
        return 1

    if not gpus:
        return 1

    if args and args[0] == "--select-best":
        picked = select_best_gpu(gpus)
        if picked is None:
            return 1
        print(picked.index)
        return 0

    sys.stdout.write(format_shell_records(gpus))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
