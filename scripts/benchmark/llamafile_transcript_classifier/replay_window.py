"""Rolling-window selection helpers for transcript replay."""

from __future__ import annotations

from scripts.benchmark.llamafile_transcript_classifier.replay_models import (
    WindowSelectContext,
)
from scripts.benchmark.llamafile_transcript_classifier.transcripts import TranscriptTurn


def build_messages(
    system_prompt: str,
    turns: list[TranscriptTurn],
    classification_task: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in turns:
        messages.append({"role": "user", "content": turn.user_text})
        messages.append({"role": "assistant", "content": turn.assistant_text})
    messages.append({"role": "user", "content": classification_task})
    return messages


def estimate_messages_tokens(
    messages: list[dict[str, str]],
    chars_per_token: float,
) -> int:
    """Rough token estimate from message character counts."""
    chars = sum(len(str(msg.get("content", ""))) for msg in messages)
    return max(1, int(chars / chars_per_token))


def select_window_turns(
    turns: list[TranscriptTurn],
    end_idx: int,
    context: WindowSelectContext,
) -> tuple[list[TranscriptTurn], int, int, bool]:
    """Pick the last n turns from prefix[:end_idx] that fit under max_context_tokens."""
    prefix = list(turns[:end_idx])
    if not prefix:
        msg = "select_window_turns requires at least one turn"
        raise ValueError(msg)

    start_offset = 0
    rolled = False
    while start_offset < len(prefix):
        visible = prefix[start_offset:]
        messages = build_messages(
            context.system_prompt, visible, context.classification_task
        )
        if context.token_counter is not None:
            tokens = context.token_counter(messages)
        else:
            tokens = estimate_messages_tokens(messages, context.chars_per_token)

        if tokens <= context.max_context_tokens:
            start_turn = visible[0].turn_index
            return visible, start_turn, len(visible), rolled

        if len(visible) <= 1:
            return visible, visible[0].turn_index, 1, rolled

        start_offset += 1
        rolled = True

    msg = "select_window_turns could not fit any turn in context window"
    raise RuntimeError(msg)
