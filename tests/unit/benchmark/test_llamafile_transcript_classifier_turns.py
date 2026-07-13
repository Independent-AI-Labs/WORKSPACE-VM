"""Unit tests for transcript turn parsing."""

import pytest

from scripts.benchmark.llamafile_transcript_classifier.transcripts import (
    discover_session_catalog,
    load_session_transcript,
    resolve_db_path,
)


def test_resolve_db_path_auto() -> None:
    db_path = resolve_db_path("auto")
    if not db_path.is_file():
        pytest.skip("opencode database not available on this host")
    assert db_path.name == "opencode.db"


def test_parse_session_turns_from_db() -> None:
    db_path = resolve_db_path("auto")
    if not db_path.is_file():
        pytest.skip("opencode database not available on this host")

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
