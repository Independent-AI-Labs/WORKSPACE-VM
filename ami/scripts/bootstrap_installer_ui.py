"""Banner + print helpers for the bootstrap installer TUI.

Stateless presentation code factored out of bootstrap_installer.py so that
file stays under the 512-line cap.
"""

from __future__ import annotations

import re
import sys

from ami.cli_components.text_input_utils import Colors
from ami.utils.banner import generate_banner_lines

CYAN = Colors.CYAN
GREEN = Colors.GREEN
YELLOW = Colors.YELLOW
RED = Colors.RED
BOLD = Colors.BOLD
DIM = "\033[2m"
RESET = Colors.RESET


_ART = generate_banner_lines()

# Box inner width (between ║ characters) — sized to fit the art
_BOX_WIDTH = max(64, max(len(line) for line in _ART) + 4)


def _visible_width(s: str) -> int:
    """Calculate visible width excluding ANSI escape codes."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return len(ansi_escape.sub("", s))


def _pad_to_width(content: str, total_width: int) -> str:
    """Pad content to total visible width."""
    visible = _visible_width(content)
    padding = total_width - visible
    return content + " " * max(0, padding)


def _box_line(content: str) -> str:
    """Create a box line with proper padding for visible width."""
    return f"║{_pad_to_width(content, _BOX_WIDTH)}║"


_BANNER_LINES = [
    f"{CYAN}╔{'═' * _BOX_WIDTH}╗",
    _box_line(""),
    *[_box_line(f" {BOLD}{line}{RESET}{CYAN}") for line in _ART],
    _box_line(""),
    _box_line(f" {YELLOW}Bootstrap Component Installer{RESET}{CYAN}"),
    _box_line(f" {DIM}Select components to install{RESET}{CYAN}"),
    _box_line(""),
    f"╚{'═' * _BOX_WIDTH}╝{RESET}",
]
BANNER = "\n".join(_BANNER_LINES)


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{CYAN}┌{'─' * 58}┐{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}{title}{RESET}{' ' * (57 - len(title))}{CYAN}│{RESET}")
    print(f"{CYAN}└{'─' * 58}┘{RESET}")


def print_status(icon: str, message: str, color: str = RESET) -> None:
    """Print a status message with icon."""
    print(f"  {color}{icon}{RESET} {message}")


def print_progress(current: int, total: int, label: str) -> None:
    """Print progress indicator."""
    bar_width = 30
    filled = int(bar_width * current / total)
    bar = f"{'█' * filled}{'░' * (bar_width - filled)}"
    print(f"\n{CYAN}[{bar}]{RESET} {current}/{total}")
    print(f"{BOLD}  ► {label}{RESET}")


def restore_terminal() -> None:
    """Restore terminal to a clean state on exit/exception."""
    sys.stdout.write(f"{RESET}")
    sys.stdout.write("\033[?25h")  # show cursor
    sys.stdout.write("\033[r")  # reset scrolling region
    sys.stdout.write("\033[999E")  # move to bottom
    sys.stdout.flush()
