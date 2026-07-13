"""Unit tests for Vulkan GPU probe and headless preference."""

from pathlib import Path

from scripts.setup.lib.vulkan_gpu_probe import (
    VulkanGpu,
    drm_monitor_counts,
    parse_vulkan_discrete_gpus,
    pci_slot_from_parts,
    select_best_gpu,
)

EXPECTED_DISCRETE_GPU_COUNT = 2
DISPLAY_GPU_MONITOR_COUNT = 2
HEADLESS_GPU_MONITOR_COUNT = 0
DISPLAY_GPU_FREE_BYTES = 800
HEADLESS_GPU_FREE_BYTES = 700

SAMPLE_VULKANINFO = """
GPU0:
deviceName        = Display GPU
pciDomain   = 0
pciBus      = 3
pciDevice   = 0
pciFunction = 0
memoryHeaps[0]:
MEMORY_HEAP_DEVICE_LOCAL_BIT
budget = 1000
usage = 200
PHYSICAL_DEVICE_TYPE_DISCRETE_GPU

GPU1:
deviceName        = Headless GPU
pciDomain   = 0
pciBus      = 9
pciDevice   = 0
pciFunction = 0
memoryHeaps[0]:
MEMORY_HEAP_DEVICE_LOCAL_BIT
budget = 800
usage = 100
PHYSICAL_DEVICE_TYPE_DISCRETE_GPU
"""


def test_pci_slot_from_parts() -> None:
    assert pci_slot_from_parts(0, 3, 0, 0) == "0000:03:00.0"
    assert pci_slot_from_parts(0, 9, 0, 0) == "0000:09:00.0"


def test_drm_monitor_counts_reads_sysfs(tmp_path: Path) -> None:
    card1 = tmp_path / "card1"
    card1.mkdir()
    (card1 / "device").mkdir()
    (card1 / "device" / "uevent").write_text(
        "PCI_SLOT_NAME=0000:03:00.0\n", encoding="utf-8"
    )
    (card1 / "card1-HDMI-A-1").mkdir()
    (card1 / "card1-HDMI-A-1" / "status").write_text("connected\n", encoding="utf-8")
    (card1 / "card1-DP-1").mkdir()
    (card1 / "card1-DP-1" / "status").write_text("disconnected\n", encoding="utf-8")

    card2 = tmp_path / "card2"
    card2.mkdir()
    (card2 / "device").mkdir()
    (card2 / "device" / "uevent").write_text(
        "PCI_SLOT_NAME=0000:09:00.0\n", encoding="utf-8"
    )

    counts = drm_monitor_counts(tmp_path)
    assert counts["0000:03:00.0"] == 1
    assert counts["0000:09:00.0"] == 0


def test_select_best_gpu_prefers_zero_monitors_over_more_vram() -> None:
    gpus = [
        VulkanGpu(0, 800, 1000, 200, "Display", "0000:03:00.0", 2),
        VulkanGpu(1, 700, 800, 100, "Headless", "0000:09:00.0", 0),
    ]
    picked = select_best_gpu(gpus)
    assert picked is not None
    assert picked.index == 1
    assert picked.monitor_count == 0


def test_select_best_gpu_falls_back_to_most_free_when_all_have_monitors() -> None:
    gpus = [
        VulkanGpu(0, 500, 1000, 500, "A", "0000:03:00.0", 1),
        VulkanGpu(1, 900, 1000, 100, "B", "0000:09:00.0", 2),
    ]
    picked = select_best_gpu(gpus)
    assert picked is not None
    assert picked.index == 1


def test_parse_vulkan_discrete_gpus_attaches_monitor_counts() -> None:
    monitors = {"0000:03:00.0": 2, "0000:09:00.0": 0}
    gpus = parse_vulkan_discrete_gpus(SAMPLE_VULKANINFO, monitor_counts=monitors)
    assert len(gpus) == EXPECTED_DISCRETE_GPU_COUNT
    by_idx = {gpu.index: gpu for gpu in gpus}
    assert by_idx[0].monitor_count == DISPLAY_GPU_MONITOR_COUNT
    assert by_idx[1].monitor_count == HEADLESS_GPU_MONITOR_COUNT
    assert by_idx[0].free_bytes == DISPLAY_GPU_FREE_BYTES
    assert by_idx[1].free_bytes == HEADLESS_GPU_FREE_BYTES
