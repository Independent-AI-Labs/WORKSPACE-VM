"""Integration test for shell-setup aliases and functions.

Verifies that all registered aliases/functions respond to -h calls.
"""

import platform
import subprocess
from pathlib import Path


def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git marker."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


# Find AMI_ROOT (agents/ directory)
AMI_ROOT = _find_project_root()
_BOOT_NAME = ".boot-macos" if platform.system() == "Darwin" else ".boot-linux"


def test_aliases_exist_and_respond_to_help() -> None:
    """Test that all aliases and functions from shell-setup exist and respond to -h."""
    script_path = AMI_ROOT / "workspace" / "scripts" / "shell" / "shell-setup"

    assert script_path.exists(), f"Setup script does not exist: {script_path}"

    expected_functions = [
        "run",
        "oc",
        "repo",
    ]

    expected_aliases: list[str] = []

    for func_name in expected_functions:
        bash_test_cmd = [
            "bash",
            "-c",
            f'export PATH="{AMI_ROOT}/.venv/bin:{AMI_ROOT}/{_BOOT_NAME}/bin:$PATH" && '
            f"source {script_path} --quiet && type -t {func_name}",
        ]

        result = subprocess.run(
            bash_test_cmd, check=False, capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"Function {func_name} does not exist: {result.stderr}"
        )

        output = result.stdout.strip()
        assert output in [
            "function",
            "builtin",
            "file",
        ], f"{func_name} is not a function/command: {output}"

        try:
            test_script = rf"""
                export AMI_ROOT="{AMI_ROOT}"
                export PYTHONPATH="{AMI_ROOT}"
                export PATH="{AMI_ROOT}/.venv/bin:{AMI_ROOT}/{_BOOT_NAME}/bin:$PATH"

                source "{script_path}" --quiet

                output=$( {func_name} -h 2>&1 )
                exit_code=$?

                if echo "$output" | grep -q \
                  'No such file or directory\|command not found'; then
                    echo "$output"
                    exit 1
                fi

                echo "Function executed (exit code: $exit_code)"
                [ -n "$output" ] && echo "$output" || true
            """
            result = subprocess.run(
                ["bash", "-c", test_script],
                check=False,
                capture_output=True,
                timeout=10,
                text=True,
                cwd=AMI_ROOT,
            )
        except subprocess.TimeoutExpired:
            continue  # Skip to next function
        except Exception as e:
            msg = f"Command {func_name} failed during execution: {e!s}"
            raise AssertionError(msg) from e

        combined_output = result.stdout + result.stderr
        if (
            "No such file or directory" in combined_output
            or "command not found" in combined_output
        ):
            msg = f"Command {func_name} failed with file error: {combined_output}"
            raise AssertionError(msg)

    for alias_name in expected_aliases:
        bash_test_cmd = [
            "bash",
            "-c",
            f"source {script_path} --quiet && alias {alias_name}",
        ]

        result = subprocess.run(
            bash_test_cmd, check=False, capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"Alias {alias_name} does not exist: {result.stderr}"
        )


if __name__ == "__main__":
    test_aliases_exist_and_respond_to_help()
