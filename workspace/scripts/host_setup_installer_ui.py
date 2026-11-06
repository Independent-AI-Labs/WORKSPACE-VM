"""Presentation helpers for the host configuration installer."""

from __future__ import annotations

from dataops.cli_components.text_input_utils import Colors

CYAN = Colors.CYAN
GREEN = Colors.GREEN
YELLOW = Colors.YELLOW
RED = Colors.RED
BOLD = Colors.BOLD
DIM = "\033[2m"
RESET = Colors.RESET


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{CYAN}┌{'─' * 58}┐{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}{title}{RESET}")
    print(f"{CYAN}└{'─' * 58}┘{RESET}")


def print_status(icon: str, message: str, color: str = RESET) -> None:
    """Print a status line."""
    print(f"  {color}{icon}{RESET} {message}")


def restore_terminal() -> None:
    """Restore the terminal after a dialog or interruption."""
    print(RESET, end="")
