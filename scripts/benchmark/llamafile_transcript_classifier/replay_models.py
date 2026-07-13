"""Named tuple models for transcript replay."""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from scripts.benchmark.llamafile_transcript_classifier.transcripts import (
    SessionTranscript,
    TranscriptTurn,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    CategoryEntry,
    JsonMap,
)


class ReplayStepResult(NamedTuple):
    turn_index: int
    turn_count: int
    window_start_turn: int
    window_turn_count: int
    window_rolled: bool
    prompt_tokens: int | None
    cache_n: int | None
    prompt_n: int | None
    ttft_ms: float | None
    total_ms: float
    completion_tokens: int | None
    tokens_per_second: float | None
    score: JsonMap
    response_preview: str


class SessionReplayResult(NamedTuple):
    session_id: str
    title: str
    bucket_tokens: int
    steps: tuple[ReplayStepResult, ...]


class WindowSelectContext(NamedTuple):
    system_prompt: str
    classification_task: str
    max_context_tokens: int
    token_counter: Callable[[list[dict[str, str]]], int] | None
    chars_per_token: float


class ReplayRuntime(NamedTuple):
    base_url: str
    session: SessionTranscript
    categories: list[CategoryEntry]
    category_ids: list[str]
    system_prompt: str
    max_context_tokens: int
    chars_per_token: float
    max_tokens: int
    temperature: float
    id_slot: int
    cache_prompt: bool
    timeout_s: float
    count_tokens: Callable[[list[dict[str, str]]], int]


class RollingWindowState(NamedTuple):
    visible: list[TranscriptTurn]
    task: str
    window_start: int
    window_count: int
    rolled: bool


class StepPrepareResult(NamedTuple):
    visible: list[TranscriptTurn]
    window_start: int
    window_count: int
    rolled: bool
    messages: list[dict[str, str]]
    prompt_tokens: int | None
    stop_early: bool


class RecordStepParams(NamedTuple):
    end_idx: int
    turn_count: int
    window_start: int
    window_count: int
    rolled: bool
    prompt_tokens: int | None


class ReplaySessionRequest(NamedTuple):
    base_url: str
    session: SessionTranscript
    bucket_tokens: int
    config: JsonMap
    category_ids: list[str]
    timeout_s: float


class TaskWindowParams(NamedTuple):
    window_start: int | None = None
    window_count: int | None = None
    rolled: bool = False
    max_context_tokens: int | None = None
