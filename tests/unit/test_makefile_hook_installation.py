"""Regression tests: hook installation is root-only in the umbrella Makefile.

User-owned hook installation was removed on 2026-08-31 (the ALLOW_UNLOCKED
bypass re-created the H5 hole it claimed to close). These tests pin the
Makefile invariants so the bypass cannot return.
"""

from __future__ import annotations

import re
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"


def _recipe(target: str, text: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:.*?\n((?:\t.*\n|[^\S\n]*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match is not None, f"target not found: {target}"
    return match.group(0)


class TestNoUserOwnedHookPath:
    def test_allow_unlocked_removed(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        assert "ALLOW_UNLOCKED" not in text

    def test_install_does_not_touch_hooks(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        assert "install-hooks" not in _recipe("install", text)

    def test_install_ci_does_not_touch_hooks(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        assert "install-hooks" not in _recipe("install-ci", text)

    def test_install_hooks_refuses_non_root(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("install-hooks", text)
        assert 'id -u)" != "0"' in recipe
        assert "exit 1" in recipe
        assert "sudo make install-hooks" in recipe

    def test_install_hooks_recursive_gate_unconditional(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("install-hooks-recursive", text)
        assert 'id -u)" != "0"' in recipe
        gate_line = next(line for line in recipe.splitlines() if "id -u" in line)
        assert "||" not in gate_line
        assert "ALLOW" not in gate_line

    def test_init_root_installs_hooks(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("init-root", text)
        assert "install-hooks-recursive" in recipe
