"""Select representative sessions by estimated context size buckets."""

from __future__ import annotations

from typing import NamedTuple

from scripts.benchmark.llamafile_transcript_classifier.transcripts import (
    SessionTranscript,
    TranscriptTurn,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    BUCKET_THRESHOLD_LARGE,
    BUCKET_THRESHOLD_MEDIUM,
    JsonMap,
)


class SelectedSession(NamedTuple):
    session_id: str
    title: str
    bucket_tokens: int
    estimated_tokens: int
    turn_count: int
    text_chars: int


class LongSessionSelectParams(NamedTuple):
    catalog: list[SessionTranscript]
    count: int
    max_context_tokens: int
    chars_per_token: float
    used_ids: set[str]
    min_estimated_tokens: int = 0


def estimate_turn_tokens(turn: TranscriptTurn, chars_per_token: float) -> int:
    """Estimate token count for one request-response turn."""
    chars = len(turn.user_text) + len(turn.assistant_text)
    return max(1, int(chars / chars_per_token))


def estimate_session_tokens(session: SessionTranscript, chars_per_token: float) -> int:
    """Estimate cumulative tokens if all turns are replayed."""
    total = 0
    for turn in session.turns:
        total += estimate_turn_tokens(turn, chars_per_token)
    return total


def _bucket_distance(estimated: int, bucket: int) -> int:
    if estimated < bucket:
        return bucket - estimated + bucket
    return abs(estimated - bucket)


def _min_estimated_for_bucket(bucket: int) -> int:
    """Minimum estimated session size to qualify for a bucket target."""
    if bucket >= BUCKET_THRESHOLD_LARGE:
        return bucket // 4
    if bucket >= BUCKET_THRESHOLD_MEDIUM:
        return bucket // 3
    return bucket // 2


def _selected_session(
    session: SessionTranscript,
    bucket_tokens: int,
    chars_per_token: float,
) -> SelectedSession:
    estimated = estimate_session_tokens(session, chars_per_token)
    return SelectedSession(
        session_id=session.session_id,
        title=session.title,
        bucket_tokens=bucket_tokens,
        estimated_tokens=estimated,
        turn_count=len(session.turns),
        text_chars=session.text_chars,
    )


def select_long_sessions(
    params: LongSessionSelectParams,
) -> list[SelectedSession]:
    """Pick the longest sessions for full incremental replay to max context."""
    ranked = sorted(
        params.catalog,
        key=lambda s: estimate_session_tokens(s, params.chars_per_token),
        reverse=True,
    )
    selected: list[SelectedSession] = []
    for session in ranked:
        if session.session_id in params.used_ids:
            continue
        estimated = estimate_session_tokens(session, params.chars_per_token)
        if params.min_estimated_tokens and estimated < params.min_estimated_tokens:
            continue
        selected.append(
            _selected_session(
                session,
                params.max_context_tokens,
                params.chars_per_token,
            )
        )
        params.used_ids.add(session.session_id)
        if len(selected) >= params.count:
            break
    return selected


def _select_explicit_sessions(
    catalog: list[SessionTranscript],
    explicit_session_ids: list[str],
    chars_per_token: float,
) -> list[SelectedSession]:
    wanted = set(explicit_session_ids)
    filtered = [s for s in catalog if s.session_id in wanted]
    if not filtered:
        msg = f"no sessions matched explicit ids: {sorted(wanted)}"
        raise KeyError(msg)
    return [
        _selected_session(
            s,
            estimate_session_tokens(s, chars_per_token),
            chars_per_token,
        )
        for s in filtered
    ]


def _pick_bucket_sessions(
    bucket: int,
    catalog: list[SessionTranscript],
    chars_per_token: float,
    used_ids: set[str],
    sessions_per_bucket: int,
) -> list[SelectedSession]:
    ranked = sorted(
        catalog,
        key=lambda s: _bucket_distance(
            estimate_session_tokens(s, chars_per_token), bucket
        ),
    )
    picked: list[SelectedSession] = []
    for session in ranked:
        if session.session_id in used_ids:
            continue
        estimated = estimate_session_tokens(session, chars_per_token)
        if estimated < _min_estimated_for_bucket(bucket):
            continue
        picked.append(_selected_session(session, bucket, chars_per_token))
        used_ids.add(session.session_id)
        if len(picked) >= sessions_per_bucket:
            return picked

    if ranked:
        reserve_pick = ranked[0]
        if reserve_pick.session_id not in used_ids:
            picked.append(_selected_session(reserve_pick, bucket, chars_per_token))
            used_ids.add(reserve_pick.session_id)
    return picked


def select_sessions_for_buckets(
    catalog: list[SessionTranscript],
    buckets: list[int],
    chars_per_token: float,
    sessions_per_bucket: int = 1,
    explicit_session_ids: list[str] | None = None,
) -> list[SelectedSession]:
    """Pick sessions whose estimated size best matches each token bucket."""
    if explicit_session_ids:
        return _select_explicit_sessions(catalog, explicit_session_ids, chars_per_token)

    selected: list[SelectedSession] = []
    used_ids: set[str] = set()
    for bucket in sorted(buckets):
        selected.extend(
            _pick_bucket_sessions(
                bucket,
                catalog,
                chars_per_token,
                used_ids,
                sessions_per_bucket,
            )
        )
    if not selected:
        msg = "session bucket selection produced zero sessions"
        raise RuntimeError(msg)
    return selected


def select_benchmark_sessions(
    catalog: list[SessionTranscript],
    config: JsonMap,
    explicit_session_ids: list[str] | None = None,
) -> list[SelectedSession]:
    """Select bucket-matched sessions plus optional long-session full replays."""
    chars_per_token = float(config.get("chars_per_token", 3.2))
    buckets = [int(x) for x in config.get("size_buckets", [1024, 2048, 4096, 8192])]
    sessions_per_bucket = int(config.get("sessions_per_bucket", 1))
    max_context_tokens = int(config.get("max_context_tokens", 8192))
    long_replays = int(config.get("long_session_replays", 0))
    long_min = int(config.get("long_session_min_estimated_tokens", 0))

    bucket_selected = select_sessions_for_buckets(
        catalog=catalog,
        buckets=buckets,
        chars_per_token=chars_per_token,
        sessions_per_bucket=sessions_per_bucket,
        explicit_session_ids=explicit_session_ids,
    )
    if explicit_session_ids or long_replays <= 0:
        return bucket_selected

    used_ids = {item.session_id for item in bucket_selected}
    long_selected = select_long_sessions(
        LongSessionSelectParams(
            catalog=catalog,
            count=long_replays,
            max_context_tokens=max_context_tokens,
            chars_per_token=chars_per_token,
            used_ids=used_ids,
            min_estimated_tokens=long_min,
        )
    )
    return [*bucket_selected, *long_selected]
