"""Incremental cached replay of transcript sessions for classification."""

from __future__ import annotations

from scripts.benchmark.llamafile_transcript_classifier.client import (
    CompletionRequest,
    count_input_tokens,
    erase_slot,
    stream_chat_completion,
)
from scripts.benchmark.llamafile_transcript_classifier.replay_models import (
    RecordStepParams,
    ReplayRuntime,
    ReplaySessionRequest,
    ReplayStepResult,
    SessionReplayResult,
    WindowSelectContext,
)
from scripts.benchmark.llamafile_transcript_classifier.replay_steps import (
    category_entries,
    prepare_step,
    record_step,
    replay_mode,
)
from scripts.benchmark.llamafile_transcript_classifier.replay_window import (
    build_messages as _build_messages,
)
from scripts.benchmark.llamafile_transcript_classifier.replay_window import (
    estimate_messages_tokens,
    select_window_turns,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    DEFAULT_MAX_CONTEXT_TOKENS,
)

__all__ = [
    "ReplaySessionRequest",
    "ReplayStepResult",
    "SessionReplayResult",
    "WindowSelectContext",
    "_build_messages",
    "estimate_messages_tokens",
    "replay_session",
    "select_window_turns",
]


def replay_session(request: ReplaySessionRequest) -> SessionReplayResult:
    """Replay turns with pinned slot, prompt caching, and optional rolling window."""
    replay_cfg = request.config.get("replay", {})
    mode = replay_mode(request.config)
    id_slot = int(replay_cfg.get("id_slot", 0))
    cache_prompt = bool(replay_cfg.get("cache_prompt", True))
    max_context_tokens = int(
        request.config.get("max_context_tokens", DEFAULT_MAX_CONTEXT_TOKENS)
    )
    chars_per_token = float(request.config.get("chars_per_token", 3.2))
    system_prompt = str(request.config.get("system_prompt", "")).strip()
    max_tokens = int(request.config.get("max_completion_tokens", 384))
    temperature = float(request.config.get("temperature", 0))

    erase_slot(request.base_url, id_slot, timeout_s=request.timeout_s)

    runtime = ReplayRuntime(
        base_url=request.base_url,
        session=request.session,
        categories=category_entries(request.config),
        category_ids=request.category_ids,
        system_prompt=system_prompt,
        max_context_tokens=max_context_tokens,
        chars_per_token=chars_per_token,
        max_tokens=max_tokens,
        temperature=temperature,
        id_slot=id_slot,
        cache_prompt=cache_prompt,
        timeout_s=request.timeout_s,
        count_tokens=lambda messages: count_input_tokens(
            request.base_url, messages, timeout_s=request.timeout_s
        ),
    )

    turn_count = len(request.session.turns)
    steps: list[ReplayStepResult] = []

    for end_idx in range(1, turn_count + 1):
        prepared = prepare_step(runtime, end_idx, turn_count, mode)
        if prepared.stop_early:
            break

        metrics = stream_chat_completion(
            CompletionRequest(
                base_url=request.base_url,
                messages=prepared.messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_s=request.timeout_s,
                id_slot=id_slot,
                cache_prompt=cache_prompt,
            )
        )
        steps.append(
            record_step(
                runtime,
                RecordStepParams(
                    end_idx=end_idx,
                    turn_count=turn_count,
                    window_start=prepared.window_start,
                    window_count=prepared.window_count,
                    rolled=prepared.rolled,
                    prompt_tokens=prepared.prompt_tokens,
                ),
                metrics,
            )
        )

        measured = (
            metrics.prompt_tokens
            if metrics.prompt_tokens is not None
            else prepared.prompt_tokens
        )
        if (
            mode == "cumulative"
            and measured is not None
            and measured > max_context_tokens
        ):
            break

    if not steps:
        msg = f"session replay produced zero steps: {request.session.session_id}"
        raise RuntimeError(msg)

    return SessionReplayResult(
        session_id=request.session.session_id,
        title=request.session.title,
        bucket_tokens=request.bucket_tokens,
        steps=tuple(steps),
    )
