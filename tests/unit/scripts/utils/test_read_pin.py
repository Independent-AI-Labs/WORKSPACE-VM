"""Unit tests for workspace/scripts/utils/read_pin.py."""

from pathlib import Path

from workspace.scripts.utils.read_pin import main, read_pin

_USAGE_EXIT_CODE = 2


def test_reads_nested_key() -> None:
    data = {"qemu": {"source_url": "https://example.test/qemu.tar.xz"}}
    assert read_pin(data, "qemu.source_url") == "https://example.test/qemu.tar.xz"


def test_missing_key_returns_none() -> None:
    assert read_pin({"qemu": {}}, "qemu.source_url") is None


def test_non_mapping_returns_none() -> None:
    assert read_pin(None, "qemu.source_url") is None


def test_main_usage_error(capsys) -> None:
    assert main([]) == _USAGE_EXIT_CODE
    assert "usage:" in capsys.readouterr().err


def test_main_prints_value(tmp_path: Path, capsys) -> None:
    pins = tmp_path / "pins.yaml"
    pins.write_text("qemu:\n  source_url: https://example.test/qemu.tar.xz\n")
    assert main([str(pins), "qemu.source_url"]) == 0
    assert "example.test" in capsys.readouterr().out


def test_main_missing_key_prints_nothing(tmp_path: Path, capsys) -> None:
    pins = tmp_path / "pins.yaml"
    pins.write_text("qemu: {}\n")
    assert main([str(pins), "qemu.source_url"]) == 0
    assert capsys.readouterr().out == ""
