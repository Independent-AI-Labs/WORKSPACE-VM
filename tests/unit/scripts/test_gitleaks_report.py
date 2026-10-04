"""Unit tests for scripts/services/gitleaks_report.py."""

import json
from pathlib import Path

import pytest

from scripts.services.gitleaks_report import count_findings

_EXPECTED_FINDINGS = 2


def test_counts_array_entries(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps([{"a": 1}, {"b": 2}]), encoding="utf-8")
    assert count_findings(report) == _EXPECTED_FINDINGS


def test_null_report_is_zero(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text("null", encoding="utf-8")
    assert count_findings(report) == 0


def test_non_array_report_raises(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    with pytest.raises(TypeError):
        count_findings(report)
