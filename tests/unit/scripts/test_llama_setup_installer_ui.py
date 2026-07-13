"""Unit tests for llama_setup_installer_ui print helpers."""

from __future__ import annotations

import re

import pytest

from workspace.scripts.llama_setup_detect import (
    BuildStepStatus,
    DetectSnapshot,
    GroupMembership,
    HardwareSnapshot,
    PrereqStatus,
    ServiceUnit,
    StackStatus,
    ToolPresence,
)
from workspace.scripts.llama_setup_installer_ui import (
    BANNER,
    CYAN,
    GREEN,
    RESET,
    _bool_icon,
    _pad_to_width,
    _visible_width,
    print_detect_snapshot,
    print_hardware_summary,
    print_prereq_summary,
    print_progress,
    print_section,
    print_service_summary,
    print_stack_summary,
    print_status,
    restore_terminal,
)

HELLO_VISIBLE_WIDTH = 5
PADDED_TARGET_WIDTH = 6


class TestFormattingHelpers:
    def test_visible_width_strips_ansi(self) -> None:
        text = f"{CYAN}hello{RESET}"
        assert _visible_width(text) == HELLO_VISIBLE_WIDTH

    def test_pad_to_width_adds_spaces(self) -> None:
        padded = _pad_to_width("hi", PADDED_TARGET_WIDTH)
        assert len(padded) == PADDED_TARGET_WIDTH

    def test_bool_icon_states(self) -> None:
        assert "✓" in _bool_icon(True)
        assert "✗" in _bool_icon(False)

    def test_banner_contains_title(self) -> None:
        assert "Llama / Hardware Setup" in BANNER


class TestPrintHelpers:
    def test_print_section(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_section("Test Section")
        output = capsys.readouterr().out
        assert "Test Section" in output
        assert "┌" in output

    def test_print_status(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_status("•", "message", GREEN)
        assert "message" in capsys.readouterr().out

    def test_print_progress(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_progress(1, 4, "step:build")
        output = capsys.readouterr().out
        assert "1/4" in output
        assert "step:build" in output

    def test_restore_terminal_writes_escape_codes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        writes: list[str] = []

        class FakeStdout:
            def write(self, text: str) -> int:
                writes.append(text)
                return len(text)

            def flush(self) -> None:
                return None

        monkeypatch.setattr("sys.stdout", FakeStdout())
        restore_terminal()
        assert any("\033[?25h" in item for item in writes)


class TestSnapshotPrinting:
    def _hardware(self, *, probe_rc: int = 0) -> HardwareSnapshot:
        return HardwareSnapshot(
            groups=GroupMembership(render=True, video=False),
            tools=ToolPresence(xpu_smi=False, vulkaninfo=True, clinfo=False),
            gpu_probe_rc=probe_rc,
            gpu_probe_lines=("Intel Arc", "driver ok"),
        )

    def test_print_hardware_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_hardware_summary(self._hardware())
        output = capsys.readouterr().out
        assert "Hardware Detection" in output
        assert "render group" in output
        assert "Intel Arc" in output

    def test_print_hardware_summary_probe_failure(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        print_hardware_summary(self._hardware(probe_rc=2))
        assert "failed (rc 2)" in capsys.readouterr().out

    def test_print_prereq_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_prereq_summary(
            (
                PrereqStatus(
                    prereq_id="vulkan_dev",
                    label="Vulkan dev",
                    satisfied=False,
                    detail="vulkaninfo missing",
                ),
            )
        )
        output = capsys.readouterr().out
        assert "Vulkan dev" in output
        assert "vulkaninfo missing" in output

    def test_print_stack_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        print_stack_summary(
            (
                StackStatus(
                    stack_id="s",
                    label="Stack",
                    build_steps=(
                        BuildStepStatus(
                            step_id="build",
                            label="Build",
                            installed=True,
                            detail="bin/llama",
                        ),
                    ),
                    ready=True,
                ),
            )
        )
        output = capsys.readouterr().out
        assert "Stack" in output
        assert "Build" in output

    def test_print_service_summary_empty(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        print_service_summary(())
        assert "no llamafile/llamaserver" in capsys.readouterr().out

    def test_print_service_summary_active_unit(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        print_service_summary((ServiceUnit(name="llamafile.service", active="active"),))
        output = capsys.readouterr().out
        assert "llamafile.service" in output
        assert "[active]" in output

    def test_print_detect_snapshot(self, capsys: pytest.CaptureFixture[str]) -> None:
        snapshot = DetectSnapshot(
            hardware=self._hardware(),
            prereqs=(),
            stacks=(),
            services=(),
        )
        print_detect_snapshot(snapshot)
        output = capsys.readouterr().out
        sections = [
            "Hardware Detection",
            "Prerequisite Status",
            "Stack Build Status",
            "Systemd Services",
        ]
        for title in sections:
            assert title in output

    def test_print_progress_zero_total_uses_full_bar(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        print_progress(0, 0, "idle")
        assert re.search(r"█{30}", capsys.readouterr().out)
