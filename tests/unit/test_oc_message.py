"""Verify oc correctly delivers welcome context to opencode agent.

The agent must receive the welcome banner properly separated
from the user's task by two actual newline characters, not literal
backslash-n text. This test validates the bash string construction
pattern used in ami/scripts/bin/oc.
"""

from __future__ import annotations

import subprocess


class TestOcMessageFormat:
    def test_dollar_single_quote_produces_real_newlines(self):
        """Verify $'\\n\\n' in bash produces actual newlines, not literal \\n."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                "WELCOME='test banner'; printf '%s' \"$WELCOME\"$'\\n\\n''Task: hello'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        assert output == "test banner\n\nTask: hello", (
            f"Expected real newlines, got: {output!r}"
        )

    def test_message_contains_real_newlines(self):
        """Verify the concatenated message has actual newline bytes."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                (
                    "WELCOME='line1\nline2'; "
                    "MSG=\"$WELCOME\"$'\\n\\n''Task: build something'; "
                    "printf '%s' \"$MSG\""
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        assert "\n\n" in output, f"Missing double newline in: {output!r}"
        assert output.endswith("Task: build something"), f"Task not at end: {output!r}"

    def test_double_quote_literal_n_is_broken(self):
        """Contrast: \\n inside double quotes produces literal text, not newlines."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                "WELCOME='test banner'; printf '%s' \"$WELCOME\\n\\nTask: hello\"",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        assert output == "test banner\\n\\nTask: hello", (
            f"Old broken format gives literal \\n: {output!r}"
        )

    def test_empty_welcome_with_task(self):
        """Verify empty welcome still produces clean task line."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                "WELCOME=''; printf '%s' \"$WELCOME\"$'\\n\\n''Task: do thing'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout
        assert output == "\n\nTask: do thing", (
            f"Empty welcome should still separate: {output!r}"
        )
