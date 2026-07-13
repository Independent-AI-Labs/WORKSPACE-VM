"""Unit tests for config discovery."""

from scripts.benchmark.llamafile_transcript_classifier.config import (
    load_config,
    resolve_config_path,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    DEFAULT_MAX_CONTEXT_TOKENS,
)

EXPECTED_SESSIONS_PER_BUCKET = 2
EXPECTED_LONG_SESSION_REPLAYS = 3


def test_resolve_transcript_classifier_config() -> None:
    config_path = resolve_config_path(None)
    assert config_path.parts[-2] == "transcript_classifier"
    config = load_config(config_path)
    assert config["max_context_tokens"] == DEFAULT_MAX_CONTEXT_TOKENS
    assert DEFAULT_MAX_CONTEXT_TOKENS in config["size_buckets"]
    assert config["sessions_per_bucket"] == EXPECTED_SESSIONS_PER_BUCKET
    assert config["long_session_replays"] == EXPECTED_LONG_SESSION_REPLAYS
    assert config["replay"]["mode"] == "rolling_window"
    assert config["replay"]["cache_prompt"] is True
