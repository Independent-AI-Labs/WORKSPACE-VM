"""Unit tests for ami/scripts/shell/banner_log.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from workspace.scripts.shell.banner_log import (
    CheckRecord,
    _write_record,
    banner_log_session,
    make_check_hook,
)

_EXPECTED_ELAPSED = 0.123


class TestBannerLogSession:
    def test_deletes_log_on_clean_session(self, tmp_path: Path) -> None:
        with banner_log_session(tmp_path, "banner") as (log, _on_failure):
            log({"event": "resolved", "name": "x"})
        files = list((tmp_path / "logs").glob("banner-banner-*.log"))
        assert len(files) == 0

    def test_keeps_log_on_failure(self, tmp_path: Path) -> None:
        with banner_log_session(tmp_path, "doctor") as (_log, on_failure):
            on_failure()
        files = list((tmp_path / "logs").glob("banner-doctor-*.log"))
        assert len(files) == 1
        first = json.loads(files[0].read_text().splitlines()[0])
        assert first["event"] == "session_start"

    def test_logs_session_metadata(self, tmp_path: Path) -> None:
        with banner_log_session(tmp_path, "doctor") as (_log, on_failure):
            on_failure()
        files = list((tmp_path / "logs").glob("banner-doctor-*.log"))
        assert len(files) == 1
        first = json.loads(files[0].read_text().splitlines()[0])
        assert first["event"] == "session_start"
        assert first["mode"] == "doctor"
        assert first["root"] == str(tmp_path)
        assert "python" in first
        assert "pid" in first

    def test_survives_oserror_on_open(self, tmp_path: Path) -> None:
        with (
            patch(
                "workspace.scripts.shell.banner_log.Path.mkdir",
                side_effect=OSError("denied"),
            ),
            banner_log_session(tmp_path, "banner") as (log, _on_failure),
        ):
            log({"event": "resolved"})  # must not raise
        assert not (tmp_path / "logs").exists() or not list(
            (tmp_path / "logs").glob("*")
        )

    def test_write_record_swallows_ioerror_on_closed_file(self, tmp_path: Path) -> None:
        path = tmp_path / "sink.log"
        fh = path.open("w", encoding="utf-8")
        fh.close()
        _write_record(fh, {"event": "dead"})  # must not raise

    def test_unserializable_record_is_swallowed(self, tmp_path: Path) -> None:
        with banner_log_session(tmp_path, "banner") as (log, on_failure):
            on_failure()
            circular: dict = {"event": "x"}
            circular["self"] = circular
            log(circular)  # must not raise
        files = list((tmp_path / "logs").glob("banner-banner-*.log"))
        assert files


class TestMakeCheckHook:
    def test_hook_writes_record_with_all_fields(self) -> None:
        captured: list[dict] = []

        def log(record: dict) -> None:
            captured.append(record)

        hook = make_check_hook(log, "ami-test")
        hook(
            CheckRecord(
                command=["/bin/echo", "x"],
                returncode=0,
                stdout="out",
                stderr="",
                elapsed_s=_EXPECTED_ELAPSED,
                healthy=True,
                version="1.2.3",
                exception=None,
            ),
        )
        assert len(captured) == 1
        record = captured[0]
        assert record["event"] == "check"
        assert record["name"] == "ami-test"
        assert record["command"] == ["/bin/echo", "x"]
        assert record["returncode"] == 0
        assert record["stdout"] == "out"
        assert record["healthy"] is True
        assert record["version"] == "1.2.3"
        assert record["exception"] is None
        assert record["elapsed_s"] == _EXPECTED_ELAPSED

    def test_hook_handles_failure_record(self) -> None:
        captured: list[dict] = []
        failures: list[None] = []

        def on_failure() -> None:
            failures.append(None)

        hook = make_check_hook(captured.append, "ami-broken", on_failure)
        hook(
            CheckRecord(
                command=["/bin/false"],
                returncode=None,
                stdout="",
                stderr="boom",
                elapsed_s=5.0,
                healthy=False,
                version=None,
                exception="TimeoutExpired",
            ),
        )
        record = captured[0]
        assert record["healthy"] is False
        assert record["exception"] == "TimeoutExpired"
        assert record["name"] == "ami-broken"
        assert len(failures) == 1

    def test_hook_healthy_does_not_call_on_failure(self) -> None:
        captured: list[dict] = []
        failures: list[None] = []

        def on_failure() -> None:
            failures.append(None)

        hook = make_check_hook(captured.append, "ami-ok", on_failure)
        hook(
            CheckRecord(
                command=["/bin/true"],
                returncode=0,
                stdout="",
                stderr="",
                elapsed_s=1.0,
                healthy=True,
                version="9.9",
                exception=None,
            ),
        )
        assert len(failures) == 0
