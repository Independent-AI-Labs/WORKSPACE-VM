"""Unit tests for transcript turn parsing."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.benchmark.llamafile_transcript_classifier.transcripts import (
    discover_session_catalog,
    load_session_transcript,
    resolve_db_path,
)


def _build_transcript_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    try:
        fixture = Path(__file__).resolve().parent / "fixtures"
        schema = (fixture / "transcript_schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema)
        conn.execute(
            (fixture / "transcript_session_insert.sql").read_text(encoding="utf-8"),
            ("ses_test", "test", "/tmp/WORKSPACE-VM"),
        )
        messages = [
            ("msg_user", "user", 1),
            ("msg_assistant", "assistant", 2),
        ]
        for message_id, role, created in messages:
            conn.execute(
                (fixture / "transcript_message_insert.sql").read_text(encoding="utf-8"),
                (message_id, "ses_test", created, json.dumps({"role": role})),
            )
        parts = [
            ("msg_user", 1, json.dumps({"type": "text", "text": "u" * 120})),
            ("msg_assistant", 2, json.dumps({"type": "text", "text": "a" * 120})),
        ]
        conn.executemany(
            (fixture / "transcript_part_insert.sql").read_text(encoding="utf-8"),
            parts,
        )
        conn.commit()
    finally:
        conn.close()
    return path


def test_resolve_db_path_auto() -> None:
    db_path = resolve_db_path("auto")
    if not db_path.is_file():
        pytest.skip("opencode database not available on this host")
    assert db_path.name == "opencode.db"


def test_parse_session_turns_from_db(tmp_path: Path) -> None:
    db_path = _build_transcript_db(tmp_path / "opencode.db")
    source = {
        "project_directory_contains": "WORKSPACE-VM",
        "min_text_chars": 200,
        "include_part_types": ["text"],
    }
    catalog = discover_session_catalog(db_path, source)
    assert catalog
    record = load_session_transcript(db_path, catalog[0].session_id, source)
    assert record.turns
    first = record.turns[0]
    assert first.user_text
    assert first.assistant_text
    assert first.turn_index == 1
