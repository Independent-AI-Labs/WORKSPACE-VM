"""Unit tests for extended report analytics."""

from scripts.benchmark.llamafile_transcript_classifier.report_analysis import (
    build_extended_summary,
)

EXPECTED_DURATION_S = 12.5
EXPECTED_STEPS_TOTAL = 2
MIN_CACHE_HIT_RATIO_AVG = 0.5
EXPECTED_PROMPT_TOKENS_MAX = 5000
EXPECTED_SESSION_SUMMARIES_COUNT = 1


def test_build_extended_summary_computes_cache_and_latency() -> None:
    report = {
        "max_context_tokens": 131072,
        "size_buckets": [4096, 8192],
        "summary": {"sessions_total": 1, "steps_passed": 2, "steps_total": 2},
        "sessions": [
            {
                "session_id": "ses_a",
                "title": "Session A",
                "bucket_tokens": 8192,
                "steps": [
                    {
                        "turn_index": 1,
                        "prompt_tokens": 1000,
                        "cache_n": 100,
                        "prompt_n": 900,
                        "ttft_ms": 120.0,
                        "total_ms": 400.0,
                        "tokens_per_second": 2.0,
                        "score": {
                            "passed": True,
                            "parsed_scores": {"sincerity": 0.5},
                        },
                    },
                    {
                        "turn_index": 2,
                        "prompt_tokens": 5000,
                        "cache_n": 4500,
                        "prompt_n": 500,
                        "ttft_ms": 80.0,
                        "total_ms": 300.0,
                        "tokens_per_second": 3.0,
                        "score": {
                            "passed": True,
                            "parsed_scores": {"sincerity": 0.6},
                        },
                    },
                ],
            }
        ],
    }
    extended = build_extended_summary(report, duration_s=EXPECTED_DURATION_S)
    assert extended["duration_s"] == EXPECTED_DURATION_S
    assert extended["steps_total"] == EXPECTED_STEPS_TOTAL
    assert extended["cache_hit_ratio_avg"] is not None
    assert extended["cache_hit_ratio_avg"] >= MIN_CACHE_HIT_RATIO_AVG
    assert extended["prompt_tokens_max"] == EXPECTED_PROMPT_TOKENS_MAX
    assert len(extended["session_summaries"]) == EXPECTED_SESSION_SUMMARIES_COUNT
    assert extended["session_summaries"][0]["steps"] == EXPECTED_STEPS_TOTAL
    assert extended["category_stats"][0]["category_id"] == "sincerity"
