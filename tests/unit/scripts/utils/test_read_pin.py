"""Unit tests for workspace/scripts/utils/read_pin.py."""

from workspace.scripts.utils.read_pin import read_pin


def test_reads_nested_key() -> None:
    data = {"qemu": {"source_url": "https://example.test/qemu.tar.xz"}}
    assert read_pin(data, "qemu.source_url") == "https://example.test/qemu.tar.xz"


def test_missing_key_returns_none() -> None:
    assert read_pin({"qemu": {}}, "qemu.source_url") is None


def test_non_mapping_returns_none() -> None:
    assert read_pin(None, "qemu.source_url") is None
