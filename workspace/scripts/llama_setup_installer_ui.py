"""Banner and print helpers for the llama-setup TUI."""

from __future__ import annotations

import re
import sys

from dataops.cli_components.text_input_utils import Colors

from workspace.scripts.llama_setup_detect import (
    DetectSnapshot,
    HardwareSnapshot,
    PrereqStatus,
    ServiceUnit,
    StackStatus,
)

CYAN = Colors.CYAN
GREEN = Colors.GREEN
YELLOW = Colors.YELLOW
RED = Colors.RED
BOLD = Colors.BOLD
DIM = "\033[2m"
RESET = Colors.RESET


def _visible_width(text: str) -> int:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return len(ansi_escape.sub("", text))


def _pad_to_width(content: str, total_width: int) -> str:
    visible = _visible_width(content)
    padding = total_width - visible
    return content + " " * max(0, padding)


def _box_line(content: str, box_width: int) -> str:
    return f"║{_pad_to_width(content, box_width)}║"


_BOX_WIDTH = 64

_BANNER_LINES = [
    f"{CYAN}╔{'═' * _BOX_WIDTH}╗",
    _box_line("", _BOX_WIDTH),
    _box_line(f" {BOLD}Llama / Hardware Setup{RESET}{CYAN}", _BOX_WIDTH),
    _box_line(
        f" {DIM}GPU prereqs, builds, bundles, systemd deploy{RESET}{CYAN}", _BOX_WIDTH
    ),
    _box_line(f" {DIM}(General bootstrap: make install){RESET}{CYAN}", _BOX_WIDTH),
    _box_line("", _BOX_WIDTH),
    f"╚{'═' * _BOX_WIDTH}╝{RESET}",
]
BANNER = "\n".join(_BANNER_LINES)


def print_section(title: str) -> None:
    print(f"\n{CYAN}┌{'─' * 58}┐{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}{title}{RESET}{' ' * (57 - len(title))}{CYAN}│{RESET}")
    print(f"{CYAN}└{'─' * 58}┘{RESET}")


def print_status(icon: str, message: str, color: str = RESET) -> None:
    print(f"  {color}{icon}{RESET} {message}")


def print_progress(current: int, total: int, label: str) -> None:
    bar_width = 30
    filled = int(bar_width * current / total) if total else bar_width
    bar = f"{'█' * filled}{'░' * (bar_width - filled)}"
    print(f"\n{CYAN}[{bar}]{RESET} {current}/{total}")
    print(f"{BOLD}  ► {label}{RESET}")


def restore_terminal() -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.write("\033[r")
    sys.stdout.flush()


def _bool_icon(value: bool) -> str:
    return f"{GREEN}✓{RESET}" if value else f"{RED}✗{RESET}"


def print_hardware_summary(hardware: HardwareSnapshot) -> None:
    print_section("Hardware Detection")
    render_state = "yes" if hardware.groups.render else "no - run newgrp render"
    print_status(_bool_icon(hardware.groups.render), f"render group: {render_state}")
    print_status(
        _bool_icon(hardware.groups.video),
        f"video group: {'yes' if hardware.groups.video else 'no'}",
    )
    print_status(
        _bool_icon(hardware.tools.xpu_smi),
        "xpu-smi installed" if hardware.tools.xpu_smi else "xpu-smi not installed",
    )
    print_status(
        _bool_icon(hardware.tools.vulkaninfo),
        "vulkaninfo available" if hardware.tools.vulkaninfo else "vulkaninfo missing",
    )
    print_status(
        _bool_icon(hardware.tools.clinfo),
        "clinfo available" if hardware.tools.clinfo else "clinfo missing",
    )
    probe_ok = hardware.gpu_probe_rc == 0
    print_status(
        _bool_icon(probe_ok),
        "Vulkan GPU probe"
        + ("" if probe_ok else f" failed (rc {hardware.gpu_probe_rc})"),
    )
    for line in hardware.gpu_probe_lines[:12]:
        print(f"    {DIM}{line}{RESET}")


def print_prereq_summary(prereqs: tuple[PrereqStatus, ...]) -> None:
    print_section("Prerequisite Status")
    for item in prereqs:
        icon = _bool_icon(item.satisfied)
        state = "ready" if item.satisfied else item.detail
        print_status(icon, f"{item.label}: {state}")


def print_stack_summary(stacks: tuple[StackStatus, ...]) -> None:
    print_section("Stack Build Status")
    for stack in stacks:
        ready_icon = _bool_icon(stack.ready)
        print_status(ready_icon, f"{stack.label}")
        for step in stack.build_steps:
            step_icon = _bool_icon(step.installed)
            print(f"      {step_icon} {step.label} {DIM}({step.detail}){RESET}")


def print_service_summary(services: tuple[ServiceUnit, ...]) -> None:
    print_section("Systemd Services")
    if not services:
        print_status("•", f"{DIM}no llamafile/llamaserver user units running{RESET}")
        return
    for unit in services:
        color = GREEN if unit.active == "active" else YELLOW
        print_status("•", f"{unit.name} [{unit.active}]", color)


def print_detect_snapshot(snapshot: DetectSnapshot) -> None:
    print_hardware_summary(snapshot.hardware)
    print_prereq_summary(snapshot.prereqs)
    print_stack_summary(snapshot.stacks)
    print_service_summary(snapshot.services)
