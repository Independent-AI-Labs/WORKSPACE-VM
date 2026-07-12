"""Unit tests for workspace.cli.process."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from workspace.cli import process as proc

_EXIT_FAILURE = 2


def test_run_raises_on_nonzero() -> None:
    with patch("workspace.cli.process.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["false"])
        with pytest.raises(subprocess.CalledProcessError):
            proc.run(["false"])


def test_run_result_returns_completed_process_on_failure() -> None:
    with patch("workspace.cli.process.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            _EXIT_FAILURE,
            ["cmd"],
            output="out",
            stderr="err",
        )
        result = proc.run_result(["cmd"], capture_output=True, text=True)
    assert result.returncode == _EXIT_FAILURE
    assert result.stdout == "out"
    assert result.stderr == "err"


def test_run_ok_false_on_called_process_error() -> None:
    with patch("workspace.cli.process.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["qemu"])
        assert proc.run_ok(["qemu"]) is False


def test_run_ok_true_on_success() -> None:
    with patch("workspace.cli.process.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(["true"], 0, "ok", "")
        assert proc.run_ok(["true"], capture_output=True, text=True) is True


def test_run_ok_rejects_output_substring() -> None:
    with patch("workspace.cli.process.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            ["qemu"],
            0,
            stdout="",
            stderr="unknown accelerator hvf",
        )
        assert (
            proc.run_ok(
                ["qemu"],
                capture_output=True,
                text=True,
                reject_in_output="unknown accelerator",
            )
            is False
        )
