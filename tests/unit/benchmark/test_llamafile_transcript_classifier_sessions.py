"""Unit tests for session bucket selection."""

from scripts.benchmark.llamafile_transcript_classifier.sessions import (
    LongSessionSelectParams,
    select_benchmark_sessions,
    select_long_sessions,
    select_sessions_for_buckets,
)
from scripts.benchmark.llamafile_transcript_classifier.transcripts import (
    SessionTranscript,
    TranscriptTurn,
)

EXPECTED_SELECTED_SESSIONS = 2
MIN_BENCHMARK_SESSIONS = 2


def _session(session_id: str, turn_chars: int, turn_count: int) -> SessionTranscript:
    turns = tuple(
        TranscriptTurn(
            turn_index=idx + 1,
            user_text="u" * turn_chars,
            assistant_text="a" * turn_chars,
        )
        for idx in range(turn_count)
    )
    body_chars = turn_chars * 2 * turn_count
    return SessionTranscript(
        session_id=session_id,
        title=session_id,
        text_chars=body_chars,
        message_count=turn_count * 2,
        turns=turns,
    )


def test_select_sessions_for_buckets_prefers_closest_size() -> None:
    catalog = [
        _session("ses_small", 100, 3),
        _session("ses_medium", 400, 4),
        _session("ses_large", 1200, 6),
    ]
    selected = select_sessions_for_buckets(
        catalog=catalog,
        buckets=[1024, 4096],
        chars_per_token=3.2,
        sessions_per_bucket=1,
    )
    assert len(selected) == EXPECTED_SELECTED_SESSIONS
    ids = {row.session_id for row in selected}
    assert "ses_medium" in ids or "ses_large" in ids


def test_explicit_session_ids_override_buckets() -> None:
    catalog = [
        _session("ses_a", 200, 2),
        _session("ses_b", 500, 3),
    ]
    selected = select_sessions_for_buckets(
        catalog=catalog,
        buckets=[1024],
        chars_per_token=3.2,
        explicit_session_ids=["ses_b"],
    )
    assert len(selected) == 1
    assert selected[0].session_id == "ses_b"


def test_select_long_sessions_picks_largest() -> None:
    catalog = [
        _session("ses_small", 100, 3),
        _session("ses_large", 1200, 6),
        _session("ses_medium", 400, 4),
    ]
    selected = select_long_sessions(
        LongSessionSelectParams(
            catalog=catalog,
            count=2,
            max_context_tokens=131072,
            chars_per_token=3.2,
            used_ids=set(),
        )
    )
    assert [row.session_id for row in selected] == ["ses_large", "ses_medium"]


def test_select_benchmark_sessions_adds_long_replays() -> None:
    catalog = [
        _session("ses_small", 100, 3),
        _session("ses_medium", 400, 4),
        _session("ses_large", 1200, 6),
    ]
    selected = select_benchmark_sessions(
        catalog=catalog,
        config={
            "chars_per_token": 3.2,
            "size_buckets": [1024],
            "sessions_per_bucket": 1,
            "max_context_tokens": 131072,
            "long_session_replays": 1,
            "long_session_min_estimated_tokens": 0,
        },
    )
    ids = {row.session_id for row in selected}
    assert "ses_large" in ids
    assert len(selected) >= MIN_BENCHMARK_SESSIONS
