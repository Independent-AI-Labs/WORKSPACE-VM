"""Tests for vulkan_gpu_probe shell record cache parsing."""

from scripts.setup.lib.vulkan_gpu_probe import (
    VulkanGpu,
    format_shell_records,
    load_cached_gpus,
    parse_shell_records,
    select_best_gpu,
)

PARSED_GPU_COUNT = 2
DISPLAY_MONITOR_COUNT = 2
HEADLESS_GPU_INDEX = 1
CACHED_FREE_BYTES = 500


def test_parse_shell_records_roundtrip() -> None:
    gpus = [
        VulkanGpu(
            index=HEADLESS_GPU_INDEX,
            free_bytes=700,
            budget_bytes=800,
            usage_bytes=100,
            device_name="Headless GPU",
            pci_slot="0000:09:00.0",
            monitor_count=0,
        ),
        VulkanGpu(
            index=0,
            free_bytes=800,
            budget_bytes=1000,
            usage_bytes=200,
            device_name="Display GPU",
            pci_slot="0000:03:00.0",
            monitor_count=DISPLAY_MONITOR_COUNT,
        ),
    ]
    text = format_shell_records(gpus)
    parsed = parse_shell_records(text)
    assert len(parsed) == PARSED_GPU_COUNT
    assert parsed[0].index == HEADLESS_GPU_INDEX
    assert parsed[1].monitor_count == DISPLAY_MONITOR_COUNT


def test_select_best_from_cached_records_prefers_headless() -> None:
    gpus = [
        VulkanGpu(0, 800, 1000, 200, "Display", "0000:03:00.0", DISPLAY_MONITOR_COUNT),
        VulkanGpu(HEADLESS_GPU_INDEX, 700, 800, 100, "Headless", "0000:09:00.0", 0),
    ]
    text = format_shell_records(gpus)
    cached = parse_shell_records(text)
    picked = select_best_gpu(cached)
    assert picked is not None
    assert picked.index == HEADLESS_GPU_INDEX


def test_load_cached_gpus_from_text(tmp_path) -> None:
    gpus = [VulkanGpu(0, CACHED_FREE_BYTES, 600, 100, "GPU", "0000:01:00.0", 0)]
    cache_file = tmp_path / "probe.cache"
    cache_file.write_text(format_shell_records(gpus), encoding="utf-8")
    loaded = load_cached_gpus(cache_file)
    assert len(loaded) == 1
    assert loaded[0].free_bytes == CACHED_FREE_BYTES
