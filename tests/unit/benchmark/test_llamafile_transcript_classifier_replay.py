"""Unit tests for message construction and rolling window selection."""

from scripts.benchmark.llamafile_transcript_classifier.replay import (
    WindowSelectContext,
    _build_messages,
    estimate_messages_tokens,
    select_window_turns,
)
from scripts.benchmark.llamafile_transcript_classifier.task import (
    ClassificationTaskParams,
    render_classification_task,
)
from scripts.benchmark.llamafile_transcript_classifier.transcripts import TranscriptTurn

EXPECTED_VISIBLE_TURNS = 2
WINDOW_START_TURN = 1
FINAL_TURN_INDEX = 3
TOTAL_TURN_COUNT = 3


def _task(turn_index: int, turn_count: int) -> str:
    return render_classification_task(
        categories=[{"id": "sincerity", "description": "Candor"}],
        params=ClassificationTaskParams(
            session_id="ses_test",
            title="Test",
            turn_index=turn_index,
            turn_count=turn_count,
        ),
    )


def test_build_messages_grows_cumulatively() -> None:
    turns = [
        TranscriptTurn(1, "hello", "hi"),
        TranscriptTurn(2, "next", "response"),
    ]
    task = _task(2, 2)
    messages = _build_messages("system", turns, task)
    assert messages[0] == {"role": "system", "content": "system"}
    assert messages[1]["role"] == "user"
    assert messages[2]["role"] == "assistant"
    assert messages[3]["role"] == "user"
    assert messages[4]["role"] == "assistant"
    assert messages[5]["role"] == "user"
    content = messages[5]["content"]
    assert "CLASSIFICATION TASK" in content
    assert "Example output" in content
    assert "scores:" in content
    assert "sincerity: 0.0" in content


def test_select_window_turns_keeps_full_prefix_when_it_fits() -> None:
    turns = [
        TranscriptTurn(1, "a" * 40, "b" * 40),
        TranscriptTurn(2, "c" * 40, "d" * 40),
    ]
    visible, start, count, rolled = select_window_turns(
        turns=turns,
        end_idx=2,
        context=WindowSelectContext(
            system_prompt="system",
            classification_task=_task(2, 2),
            max_context_tokens=10_000,
            token_counter=None,
            chars_per_token=3.2,
        ),
    )
    assert len(visible) == EXPECTED_VISIBLE_TURNS
    assert start == WINDOW_START_TURN
    assert count == EXPECTED_VISIBLE_TURNS
    assert rolled is False


def test_final_task_with_window_metadata_still_fits_after_trim() -> None:
    turns = [
        TranscriptTurn(1, "x" * 3000, "y" * 3000),
        TranscriptTurn(2, "a" * 3000, "b" * 3000),
        TranscriptTurn(3, "c" * 400, "d" * 400),
    ]
    max_tokens = 3500
    sizing_task = render_classification_task(
        categories=[{"id": "sincerity", "description": "Candor"}],
        params=ClassificationTaskParams(
            session_id="ses_test",
            title="Test",
            turn_index=3,
            turn_count=3,
            window_start_turn=1,
            window_turn_count=3,
            window_rolled=True,
            max_context_tokens=max_tokens,
        ),
    )
    visible, start, count, rolled = select_window_turns(
        turns=turns,
        end_idx=3,
        context=WindowSelectContext(
            system_prompt="system",
            classification_task=sizing_task,
            max_context_tokens=max_tokens,
            token_counter=None,
            chars_per_token=3.2,
        ),
    )
    final_task = render_classification_task(
        categories=[{"id": "sincerity", "description": "Candor"}],
        params=ClassificationTaskParams(
            session_id="ses_test",
            title="Test",
            turn_index=3,
            turn_count=3,
            window_start_turn=start,
            window_turn_count=count,
            window_rolled=rolled,
            max_context_tokens=max_tokens,
        ),
    )
    messages = _build_messages("system", visible, final_task)
    while len(visible) > 1:
        measured = estimate_messages_tokens(messages, 3.2)
        if measured <= max_tokens:
            break
        visible = visible[1:]
        final_task = render_classification_task(
            categories=[{"id": "sincerity", "description": "Candor"}],
            params=ClassificationTaskParams(
                session_id="ses_test",
                title="Test",
                turn_index=3,
                turn_count=3,
                window_start_turn=visible[0].turn_index,
                window_turn_count=len(visible),
                window_rolled=True,
                max_context_tokens=max_tokens,
            ),
        )
        messages = _build_messages("system", visible, final_task)
    assert estimate_messages_tokens(messages, 3.2) <= max_tokens
    assert visible[-1].turn_index == FINAL_TURN_INDEX


def test_select_window_turns_trims_oldest_turns_to_fit_budget() -> None:
    turns = [
        TranscriptTurn(1, "x" * 4000, "y" * 4000),
        TranscriptTurn(2, "a" * 4000, "b" * 4000),
        TranscriptTurn(3, "c" * 400, "d" * 400),
    ]
    max_tokens = 3000
    visible, start, count, rolled = select_window_turns(
        turns=turns,
        end_idx=3,
        context=WindowSelectContext(
            system_prompt="system",
            classification_task=_task(3, 3),
            max_context_tokens=max_tokens,
            token_counter=None,
            chars_per_token=3.2,
        ),
    )
    messages = _build_messages("system", visible, _task(3, 3))
    assert estimate_messages_tokens(messages, 3.2) <= max_tokens
    assert start > WINDOW_START_TURN
    assert count < TOTAL_TURN_COUNT
    assert rolled is True
    assert visible[-1].turn_index == FINAL_TURN_INDEX
