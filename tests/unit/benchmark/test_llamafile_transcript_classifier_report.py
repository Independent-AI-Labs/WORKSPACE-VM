"""Unit tests for growth-oriented report generation."""

from pathlib import Path

from scripts.benchmark.llamafile_transcript_classifier.replay import (
    ReplayStepResult,
    SessionReplayResult,
)
from scripts.benchmark.llamafile_transcript_classifier.report import (
    render_markdown,
    summarize_replay_results,
)

EXPECTED_STEPS_TOTAL = 3
EXPECTED_STEPS_PASSED = 2
MIN_SIZE_BUCKETS = 2
EXPECTED_GROWTH_CURVE_LEN = 3


def _step(
    turn: int, prompt_tokens: int, cache_n: int, passed: bool
) -> ReplayStepResult:
    return ReplayStepResult(
        turn_index=turn,
        turn_count=3,
        window_start_turn=1,
        window_turn_count=turn,
        window_rolled=False,
        prompt_tokens=prompt_tokens,
        cache_n=cache_n,
        prompt_n=50,
        ttft_ms=100.0 + turn * 20,
        total_ms=400.0 + turn * 50,
        completion_tokens=80,
        tokens_per_second=2.5,
        score={
            "passed": passed,
            "yaml_ok": passed,
            "categories_ok": passed,
            "range_ok": passed,
            "parsed_scores": {"sincerity": 0.5},
            "notes": "ok" if passed else "missing category",
        },
        response_preview="scores:\n  sincerity: 0.5",
    )


def test_summarize_replay_results_buckets_by_prompt_tokens() -> None:
    sessions = [
        SessionReplayResult(
            session_id="ses_a",
            title="Session A",
            bucket_tokens=2048,
            steps=(
                _step(1, 900, 0, True),
                _step(2, 1800, 850, True),
                _step(3, 3500, 1700, False),
            ),
        )
    ]
    summary = summarize_replay_results(sessions, [1024, 2048, 4096, 8192])
    assert summary["steps_total"] == EXPECTED_STEPS_TOTAL
    assert summary["steps_passed"] == EXPECTED_STEPS_PASSED
    assert len(summary["by_size_bucket"]) >= MIN_SIZE_BUCKETS
    assert len(summary["growth_curve"]) == EXPECTED_GROWTH_CURVE_LEN


def test_render_markdown_includes_growth_sections() -> None:
    sessions = [
        SessionReplayResult(
            session_id="ses_a",
            title="Session A",
            bucket_tokens=2048,
            steps=(_step(1, 900, 0, True),),
        )
    ]
    summary = summarize_replay_results(sessions, [1024, 2048, 4096, 8192])
    report = {
        "benchmark_name": "llamafile-transcript-classifier",
        "base_url": "http://127.0.0.1:8765",
        "config_path": "benchmarks/llamafile/transcript_classifier/benchmark.yaml",
        "finished_at": "2026-07-13T12:00:00Z",
        "max_context_tokens": 32768,
        "replay_mode": "rolling_window",
        "categories": ["sincerity"],
        "cache_probe": {"cache_working": True, "second_cache_n": 120},
        "summary": summary,
        "sessions": [
            {
                "session_id": s.session_id,
                "title": s.title,
                "bucket_tokens": s.bucket_tokens,
                "steps": [
                    {
                        "turn_index": step.turn_index,
                        "window_start_turn": step.window_start_turn,
                        "window_turn_count": step.window_turn_count,
                        "window_rolled": step.window_rolled,
                        "prompt_tokens": step.prompt_tokens,
                        "cache_n": step.cache_n,
                        "prompt_n": step.prompt_n,
                        "ttft_ms": step.ttft_ms,
                        "total_ms": step.total_ms,
                        "tokens_per_second": step.tokens_per_second,
                        "score": step.score,
                        "response_preview": step.response_preview,
                    }
                    for step in s.steps
                ],
            }
            for s in sessions
        ],
        "transcript_source": {
            "db_path": str(Path.home() / ".local/share/opencode/opencode.db"),
            "catalog_size": 28,
            "selected": [
                {
                    "session_id": "ses_a",
                    "title": "Session A",
                    "bucket_tokens": 2048,
                    "estimated_tokens": 2000,
                    "turn_count": 3,
                    "text_chars": 5000,
                }
            ],
        },
    }
    md = render_markdown(report)
    assert "Incremental Transcript Classifier Report" in md
    assert "## Executive Summary" in md
    assert "## Context Growth Curves" in md
    assert "## Latency and Cache Scaling" in md
    assert "Preflight cache probe" in md
    assert "| Window |" in md
