"""Unit tests for workspace.scripts.utils.sys_info."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from workspace.scripts.utils.sys_info import (
    COLOR_IDS,
    ProgressBar,
    get_size_str,
    main,
)

_ERR_MSG = "unavailable"

_ANSI = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


class TestGetSizeStr:
    def test_bytes(self) -> None:
        assert get_size_str(0) == "0.0B"
        assert get_size_str(512) == "512.0B"
        assert get_size_str(1023) == "1023.0B"

    def test_kilobytes(self) -> None:
        assert get_size_str(1024) == "1.0KB"
        assert get_size_str(2048) == "2.0KB"

    def test_megabytes(self) -> None:
        assert get_size_str(1024 * 1024) == "1.0MB"

    def test_gigabytes(self) -> None:
        assert get_size_str(1024 * 1024 * 1024) == "1.0GB"

    def test_terabytes(self) -> None:
        assert get_size_str(1024**4) == "1.0TB"

    def test_petabytes(self) -> None:
        assert get_size_str(1024**5) == "1.0PB"

    def test_large_still_petabytes(self) -> None:
        assert get_size_str(1024**6) == "1024.0PB"


class TestProgressBarColorPair:
    def setup_method(self) -> None:
        self.bar = ProgressBar(width=20)

    def test_green(self) -> None:
        pair = self.bar.get_color_pair(10)
        assert pair[0] == COLOR_IDS["green"][0]
        assert pair[1] == COLOR_IDS["green"][1]

    def test_green_boundary(self) -> None:
        pair = self.bar.get_color_pair(39.9)
        assert pair[0] == COLOR_IDS["green"][0]

    def test_yellow(self) -> None:
        pair = self.bar.get_color_pair(45)
        assert pair[0] == COLOR_IDS["yellow"][0]

    def test_yellow_boundary(self) -> None:
        pair = self.bar.get_color_pair(59.9)
        assert pair[0] == COLOR_IDS["yellow"][0]

    def test_orange(self) -> None:
        pair = self.bar.get_color_pair(65)
        assert pair[0] == COLOR_IDS["orange"][0]

    def test_orange_boundary(self) -> None:
        pair = self.bar.get_color_pair(79.9)
        assert pair[0] == COLOR_IDS["orange"][0]

    def test_red(self) -> None:
        pair = self.bar.get_color_pair(85)
        assert pair[0] == COLOR_IDS["red"][0]

    def test_red_boundary(self) -> None:
        pair = self.bar.get_color_pair(80)
        assert pair[0] == COLOR_IDS["red"][0]

    def test_full(self) -> None:
        pair = self.bar.get_color_pair(100)
        assert pair[0] == COLOR_IDS["red"][0]


class TestProgressBarRender:
    def test_render_zero_percent(self) -> None:
        bar = ProgressBar(width=20)
        plain = _strip_ansi(bar.render(0, "Test", "0.0B / 1.0GB"))
        assert "Test" in plain
        assert "0.0%" in plain

    def test_render_full_percent(self) -> None:
        bar = ProgressBar(width=20)
        plain = _strip_ansi(bar.render(100, "Test", "1.0GB / 1.0GB"))
        assert "100.0%" in plain

    def test_render_negative_clamped(self) -> None:
        bar = ProgressBar(width=20)
        plain = _strip_ansi(bar.render(-50, "Test", "val"))
        assert "0.0%" in plain

    def test_render_above_100_clamped(self) -> None:
        bar = ProgressBar(width=20)
        plain = _strip_ansi(bar.render(150, "Test", "val"))
        assert "100.0%" in plain

    def test_render_mid_percent(self) -> None:
        bar = ProgressBar(width=20)
        plain = _strip_ansi(bar.render(50, "Disk", "500MB / 1GB"))
        assert "Disk" in plain
        assert "50.0%" in plain
        assert "500MB / 1GB" in plain

    def test_render_narrow_bar(self) -> None:
        bar = ProgressBar(width=2)
        plain = _strip_ansi(bar.render(50, "X", "Y"))
        assert "X" in plain
        assert "Y" in plain

    def test_render_custom_filled_char(self) -> None:
        bar = ProgressBar(width=20, filled_char="#")
        plain = _strip_ansi(bar.render(50, "T", "V"))
        assert "#" in plain

    def test_render_custom_label_width(self) -> None:
        bar = ProgressBar(width=20)
        plain = _strip_ansi(bar.render(50, "ABC", "val", label_width=10))
        assert "ABC" in plain


class TestSysInfoMain:
    def test_main_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        disk_usage = MagicMock()
        disk_usage.percent = 55.0
        disk_usage.used = 500 * 1024**3
        disk_usage.total = 1000 * 1024**3

        virtual_mem = MagicMock()
        virtual_mem.percent = 70.0
        virtual_mem.used = 8 * 1024**3
        virtual_mem.total = 16 * 1024**3

        monkeypatch.setattr(
            "workspace.scripts.utils.sys_info.psutil.disk_usage", lambda _: disk_usage
        )
        monkeypatch.setattr(
            "workspace.scripts.utils.sys_info.psutil.virtual_memory",
            lambda: virtual_mem,
        )
        monkeypatch.setattr(
            "workspace.scripts.utils.sys_info.psutil.cpu_percent", lambda interval: 45.0
        )
        monkeypatch.setattr(
            "workspace.scripts.utils.sys_info.psutil.cpu_count", lambda: 8
        )

        main()
        out = capsys.readouterr().out
        assert "System Status" in out
        assert "Storage" in out
        assert "Memory" in out
        assert "CPU" in out

    def test_main_psutil_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:

        def raise_error(_path: object) -> None:
            raise RuntimeError(_ERR_MSG)

        monkeypatch.setattr(
            "workspace.scripts.utils.sys_info.psutil.disk_usage", raise_error
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "Error:" in out
