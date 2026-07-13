"""Per-turn preparation and recording for transcript replay."""

from __future__ import annotations

import sys
from collections.abc import Callable

from scripts.benchmark.llamafile_transcript_classifier.client import CompletionMetrics
from scripts.benchmark.llamafile_transcript_classifier.replay_models import (
    RecordStepParams,
    ReplayRuntime,
    ReplayStepResult,
    RollingWindowState,
    StepPrepareResult,
    TaskWindowParams,
    WindowSelectContext,
)
from scripts.benchmark.llamafile_transcript_classifier.replay_window import (
    build_messages,
    estimate_messages_tokens,
    select_window_turns,
)
from scripts.benchmark.llamafile_transcript_classifier.score import score_answer
from scripts.benchmark.llamafile_transcript_classifier.task import (
    ClassificationTaskParams,
    render_classification_task,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    CategoryEntry,
    JsonMap,
)


def replay_mode(config: JsonMap) -> str:
    replay_cfg = config.get("replay", {})
    mode = str(replay_cfg.get("mode", "rolling_window")).strip().lower()
    if mode in {"rolling", "rolling_window", "window"}:
        return "rolling_window"
    if mode in {"cumulative", "grow"}:
        return "cumulative"
    msg = f"unsupported replay mode: {mode}"
    raise ValueError(msg)


def category_entries(config: JsonMap) -> list[CategoryEntry]:
    raw = config.get("categories", [])
    if not isinstance(raw, list):
        return []
    return [
        {
            "id": str(item["id"]),
            "description": str(item.get("description", "")),
        }
        for item in raw
        if isinstance(item, dict) and "id" in item
    ]


def safe_token_count(
    counter: Callable[[list[dict[str, str]]], int],
    messages: list[dict[str, str]],
    chars_per_token: float,
) -> int:
    try:
        return counter(messages)
    except (OSError, RuntimeError, TimeoutError, ValueError):
        return estimate_messages_tokens(messages, chars_per_token)


def task_params(
    runtime: ReplayRuntime,
    end_idx: int,
    turn_count: int,
    window: TaskWindowParams | None = None,
) -> ClassificationTaskParams:
    window_params = window if window is not None else TaskWindowParams()
    return ClassificationTaskParams(
        session_id=runtime.session.session_id,
        title=runtime.session.title,
        turn_index=end_idx,
        turn_count=turn_count,
        window_start_turn=window_params.window_start,
        window_turn_count=window_params.window_count,
        window_rolled=window_params.rolled,
        max_context_tokens=(
            runtime.max_context_tokens
            if window_params.max_context_tokens is None
            else window_params.max_context_tokens
        ),
    )


def trim_rolling_window(
    runtime: ReplayRuntime,
    state: RollingWindowState,
    end_idx: int,
    turn_count: int,
) -> tuple[RollingWindowState, list[dict[str, str]]]:
    visible = state.visible
    task = state.task
    window_start = state.window_start
    window_count = state.window_count
    rolled = state.rolled
    messages = build_messages(runtime.system_prompt, visible, task)
    while len(visible) > 1:
        measured = safe_token_count(
            runtime.count_tokens, messages, runtime.chars_per_token
        )
        if measured <= runtime.max_context_tokens:
            break
        visible = visible[1:]
        rolled = True
        window_start = visible[0].turn_index
        window_count = len(visible)
        task = render_classification_task(
            runtime.categories,
            task_params(
                runtime,
                end_idx,
                turn_count,
                TaskWindowParams(
                    window_start=window_start,
                    window_count=window_count,
                    rolled=rolled,
                ),
            ),
        )
        messages = build_messages(runtime.system_prompt, visible, task)
    return (
        RollingWindowState(visible, task, window_start, window_count, rolled),
        messages,
    )


def prepare_rolling_step(
    runtime: ReplayRuntime,
    end_idx: int,
    turn_count: int,
) -> StepPrepareResult:
    sizing_task = render_classification_task(
        runtime.categories,
        task_params(
            runtime,
            end_idx,
            turn_count,
            TaskWindowParams(
                window_start=1,
                window_count=end_idx,
                rolled=end_idx > 1,
            ),
        ),
    )
    visible, window_start, window_count, rolled = select_window_turns(
        turns=list(runtime.session.turns),
        end_idx=end_idx,
        context=WindowSelectContext(
            system_prompt=runtime.system_prompt,
            classification_task=sizing_task,
            max_context_tokens=runtime.max_context_tokens,
            token_counter=runtime.count_tokens,
            chars_per_token=runtime.chars_per_token,
        ),
    )
    task = render_classification_task(
        runtime.categories,
        task_params(
            runtime,
            end_idx,
            turn_count,
            TaskWindowParams(
                window_start=window_start,
                window_count=window_count,
                rolled=rolled,
            ),
        ),
    )
    state, messages = trim_rolling_window(
        runtime,
        RollingWindowState(visible, task, window_start, window_count, rolled),
        end_idx,
        turn_count,
    )
    prompt_tokens = safe_token_count(
        runtime.count_tokens, messages, runtime.chars_per_token
    )
    return StepPrepareResult(
        visible=state.visible,
        window_start=state.window_start,
        window_count=state.window_count,
        rolled=state.rolled,
        messages=messages,
        prompt_tokens=prompt_tokens,
        stop_early=False,
    )


def prepare_cumulative_step(
    runtime: ReplayRuntime,
    end_idx: int,
    turn_count: int,
) -> StepPrepareResult:
    visible = list(runtime.session.turns[:end_idx])
    window_start = visible[0].turn_index
    window_count = len(visible)
    task = render_classification_task(
        runtime.categories,
        task_params(runtime, end_idx, turn_count),
    )
    messages = build_messages(runtime.system_prompt, visible, task)
    prompt_tokens: int | None = None
    try:
        prompt_tokens = runtime.count_tokens(messages)
    except (OSError, RuntimeError, TimeoutError, ValueError):
        prompt_tokens = None
    stop = prompt_tokens is not None and prompt_tokens > runtime.max_context_tokens
    return StepPrepareResult(
        visible=visible,
        window_start=window_start,
        window_count=window_count,
        rolled=False,
        messages=messages,
        prompt_tokens=prompt_tokens,
        stop_early=stop,
    )


def prepare_step(
    runtime: ReplayRuntime,
    end_idx: int,
    turn_count: int,
    mode: str,
) -> StepPrepareResult:
    if mode == "rolling_window":
        return prepare_rolling_step(runtime, end_idx, turn_count)
    return prepare_cumulative_step(runtime, end_idx, turn_count)


def preview_response(text: str, limit: int = 240) -> str:
    preview = text.strip().replace("\n", " ")
    if len(preview) > limit:
        return preview[:limit] + "..."
    return preview


def record_step(
    runtime: ReplayRuntime,
    params: RecordStepParams,
    metrics: CompletionMetrics,
) -> ReplayStepResult:
    measured = (
        metrics.prompt_tokens
        if metrics.prompt_tokens is not None
        else params.prompt_tokens
    )
    cache_n = metrics.cache_n if metrics.cache_n is not None else 0
    ttft_label = f"{metrics.ttft_ms:.0f}ms" if metrics.ttft_ms is not None else "n/a"
    roll_label = "rolled" if params.rolled else "grow"
    print(
        f"  turn {params.end_idx}/{params.turn_count}: "
        f"window={params.window_start}-{params.end_idx} "
        f"({params.window_count} pairs, {roll_label}) prompt={measured} "
        f"cache={cache_n} ttft={ttft_label} total={metrics.total_ms:.0f}ms",
        file=sys.stderr,
        flush=True,
    )
    score = score_answer(metrics.response_text, category_ids=runtime.category_ids)
    return ReplayStepResult(
        turn_index=params.end_idx,
        turn_count=params.turn_count,
        window_start_turn=params.window_start,
        window_turn_count=params.window_count,
        window_rolled=params.rolled,
        prompt_tokens=metrics.prompt_tokens
        if metrics.prompt_tokens is not None
        else params.prompt_tokens,
        cache_n=metrics.cache_n,
        prompt_n=metrics.prompt_n,
        ttft_ms=metrics.ttft_ms,
        total_ms=metrics.total_ms,
        completion_tokens=metrics.completion_tokens,
        tokens_per_second=metrics.tokens_per_second,
        score={
            "passed": score.passed,
            "yaml_ok": score.yaml_ok,
            "categories_ok": score.categories_ok,
            "range_ok": score.range_ok,
            "parsed_scores": score.parsed_scores,
            "notes": score.notes,
        },
        response_preview=preview_response(metrics.response_text),
    )
