"""Extract OpenCode SQLite transcripts and parse request-response turns."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import NamedTuple

from scripts.benchmark.llamafile_transcript_classifier.types import JsonMap, JsonValue

DEFAULT_DB_RELATIVE = ".local/share/opencode/opencode.db"


class TranscriptTurn(NamedTuple):
    turn_index: int
    user_text: str
    assistant_text: str


class SessionTranscript(NamedTuple):
    session_id: str
    title: str
    text_chars: int
    message_count: int
    turns: tuple[TranscriptTurn, ...]


def resolve_db_path(value: str | Path | None) -> Path:
    """Resolve OpenCode DB path from config value or default location."""
    if value is None or str(value).strip().lower() == "auto":
        path = Path.home() / DEFAULT_DB_RELATIVE
    else:
        path = Path(str(value)).expanduser()
    if not path.is_file():
        msg = f"opencode database not found: {path}"
        raise FileNotFoundError(msg)
    return path


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _part_text(payload: dict[str, JsonValue], allowed: set[str]) -> str:
    part_type = str(payload.get("type", ""))
    if part_type not in allowed:
        return ""
    if part_type == "text":
        text = payload.get("text")
        return text.strip() if isinstance(text, str) else ""
    return ""


def _message_text(part_rows: list[sqlite3.Row], allowed: set[str]) -> str:
    parts: list[str] = []
    for row in part_rows:
        payload = json.loads(row["part_data"])
        if not isinstance(payload, dict):
            continue
        text = _part_text(payload, allowed)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def parse_session_turns(
    conn: sqlite3.Connection,
    session_id: str,
    include_part_types: list[str] | None = None,
) -> list[TranscriptTurn]:
    """Parse a session into user/assistant request-response turn pairs."""
    allowed = set(include_part_types or ["text"])
    message_rows = conn.execute(
        """
        SELECT m.id AS message_id,
               m.time_created AS msg_ts,
               json_extract(m.data, '$.role') AS role
        FROM message m
        WHERE m.session_id = ?
        ORDER BY m.time_created
        """,
        (session_id,),
    ).fetchall()

    turns: list[TranscriptTurn] = []
    turn_index = 0
    idx = 0
    while idx < len(message_rows):
        row = message_rows[idx]
        role = str(row["role"] or "")
        if role != "user":
            idx += 1
            continue

        user_id = row["message_id"]
        user_parts = conn.execute(
            """
            SELECT p.data AS part_data, p.time_created AS part_ts
            FROM part p
            WHERE p.message_id = ?
              AND json_valid(p.data)
            ORDER BY p.time_created
            """,
            (user_id,),
        ).fetchall()
        user_text = _message_text(user_parts, allowed)
        idx += 1

        assistant_chunks: list[str] = []
        while idx < len(message_rows):
            next_row = message_rows[idx]
            next_role = str(next_row["role"] or "")
            if next_role == "user":
                break
            if next_role == "assistant":
                assistant_parts = conn.execute(
                    """
                    SELECT p.data AS part_data, p.time_created AS part_ts
                    FROM part p
                    WHERE p.message_id = ?
                      AND json_valid(p.data)
                    ORDER BY p.time_created
                    """,
                    (next_row["message_id"],),
                ).fetchall()
                assistant_text = _message_text(assistant_parts, allowed)
                if assistant_text:
                    assistant_chunks.append(assistant_text)
            idx += 1

        assistant_text = "\n\n".join(assistant_chunks)
        if user_text and assistant_text:
            turn_index += 1
            turns.append(
                TranscriptTurn(
                    turn_index=turn_index,
                    user_text=user_text,
                    assistant_text=assistant_text,
                )
            )
    return turns


def load_session_transcript(
    db_path: Path,
    session_id: str,
    source: JsonMap,
) -> SessionTranscript:
    """Load one session and parse it into cumulative replay turns."""
    include_part_types = [str(x) for x in source.get("include_part_types", ["text"])]
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT s.id, s.title, COUNT(DISTINCT m.id) AS message_count
            FROM session s
            LEFT JOIN message m ON m.session_id = s.id
            WHERE s.id = ?
            GROUP BY s.id
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            msg = f"session not found: {session_id}"
            raise FileNotFoundError(msg)
        turns = parse_session_turns(conn, session_id, include_part_types)
        if not turns:
            msg = f"session has no replayable turns: {session_id}"
            raise RuntimeError(msg)
        body_chars = sum(
            len(turn.user_text) + len(turn.assistant_text) for turn in turns
        )
        return SessionTranscript(
            session_id=session_id,
            title=str(row["title"] or session_id),
            text_chars=body_chars,
            message_count=int(row["message_count"] or 0),
            turns=tuple(turns),
        )
    finally:
        conn.close()


def discover_session_catalog(
    db_path: Path,
    source: JsonMap,
) -> list[SessionTranscript]:
    """Discover sessions and parse turns for bucket selection."""
    project_filter = str(source.get("project_directory_contains", "")).strip()
    min_chars = int(source.get("min_text_chars", 200))
    include_part_types = [str(x) for x in source.get("include_part_types", ["text"])]

    where = "1=1"
    params: list[str | int] = []
    if project_filter:
        where += " AND s.directory LIKE ?"
        params.append(f"%{project_filter}%")

    conn = _connect(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT s.id, s.title,
                   COUNT(DISTINCT m.id) AS message_count,
                   SUM(LENGTH(COALESCE(json_extract(p.data, '$.text'), '')))
                       AS text_chars
            FROM session s
            JOIN message m ON m.session_id = s.id
            JOIN part p ON p.message_id = m.id
            WHERE {where}
              AND json_extract(p.data, '$.type') = 'text'
            GROUP BY s.id
            HAVING text_chars >= ?
            ORDER BY text_chars ASC
            """,
            (*params, min_chars),
        ).fetchall()

        catalog: list[SessionTranscript] = []
        for row in rows:
            session_id = str(row["id"])
            turns = parse_session_turns(conn, session_id, include_part_types)
            if not turns:
                continue
            body_chars = sum(
                len(turn.user_text) + len(turn.assistant_text) for turn in turns
            )
            if body_chars < min_chars:
                continue
            catalog.append(
                SessionTranscript(
                    session_id=session_id,
                    title=str(row["title"] or session_id),
                    text_chars=body_chars,
                    message_count=int(row["message_count"]),
                    turns=tuple(turns),
                )
            )
        if not catalog:
            msg = "transcript discovery produced zero replayable sessions"
            raise RuntimeError(msg)
        return catalog
    finally:
        conn.close()


def sync_fixture_cache(
    repo_root: Path,
    db_path: Path,
    source: JsonMap,
    catalog: list[SessionTranscript],
) -> Path:
    """Write turn summaries and manifest under fixtures_dir."""
    fixtures_dir_value = str(source.get("fixtures_dir", "")).strip()
    if not fixtures_dir_value:
        msg = "transcript_source.fixtures_dir is required for fixture sync"
        raise ValueError(msg)
    fixtures_dir = repo_root / fixtures_dir_value
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    manifest_lines = [
        "# Auto-generated OpenCode transcript fixtures.",
        f"db_path: {db_path}",
        "sessions:",
    ]
    for record in catalog:
        fixture_path = fixtures_dir / f"{record.session_id}.txt"
        body_lines: list[str] = []
        for turn in record.turns:
            body_lines.append(f"[user] {turn.user_text}")
            body_lines.append(f"[assistant] {turn.assistant_text}")
        fixture_path.write_text("\n\n".join(body_lines) + "\n", encoding="utf-8")
        manifest_lines.append(f"  - id: {record.session_id}")
        manifest_lines.append(f"    title: {record.title!r}")
        manifest_lines.append(f"    text_chars: {record.text_chars}")
        manifest_lines.append(f"    turn_count: {len(record.turns)}")
        manifest_lines.append(f"    message_count: {record.message_count}")
        manifest_lines.append(
            f"    file: {fixture_path.relative_to(repo_root).as_posix()}"
        )

    manifest_path = fixtures_dir / "manifest.yaml"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return fixtures_dir
