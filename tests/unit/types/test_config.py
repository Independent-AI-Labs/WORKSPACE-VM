"""Unit tests for workspace.types.config models."""

from unittest.mock import MagicMock

from workspace.types.config import AgentConfig, StreamCallback
from workspace.types.events import StreamEvent

_DEFAULT_TIMEOUT = 180
_CUSTOM_TIMEOUT = 300


class TestStreamCallback:
    def test_is_callable_type(self) -> None:
        def handler(event: StreamEvent) -> None:
            pass

        _callback: StreamCallback = handler
        assert _callback is not None

    def test_none_value(self) -> None:
        cb: StreamCallback = None
        assert cb is None


class TestAgentConfig:
    def test_minimal_construction(self) -> None:
        provider = MagicMock()
        config = AgentConfig(model="gpt-4", provider=provider)
        assert config.model == "gpt-4"
        assert config.provider is provider

    def test_default_values(self) -> None:
        provider = MagicMock()
        config = AgentConfig(model="gpt-4", provider=provider)
        assert config.session_id is None
        assert config.allowed_tools is None
        assert config.enable_hooks is True
        assert config.enable_streaming is False
        assert config.timeout == _DEFAULT_TIMEOUT
        assert config.mcp_servers is None
        assert config.capture_content is False
        assert config.stream_callback is None

    def test_all_fields_populated(self) -> None:
        provider = MagicMock()

        def cb(event: StreamEvent) -> None:
            pass

        config = AgentConfig(
            model="claude-3",
            provider=provider,
            session_id="sess-001",
            allowed_tools=["tool_a", "tool_b"],
            enable_hooks=False,
            enable_streaming=True,
            timeout=300,
            mcp_servers=[],
            capture_content=True,
            stream_callback=cb,
        )
        assert config.model == "claude-3"
        assert config.session_id == "sess-001"
        assert config.allowed_tools == ["tool_a", "tool_b"]
        assert config.enable_hooks is False
        assert config.enable_streaming is True
        assert config.timeout == _CUSTOM_TIMEOUT
        assert config.mcp_servers == []
        assert config.capture_content is True
        assert config.stream_callback is cb

    def test_stream_callback_none_default(self) -> None:
        provider = MagicMock()
        config = AgentConfig(model="gpt-4", provider=provider)
        assert config.stream_callback is None

    def test_capture_content_defaults_false(self) -> None:
        provider = MagicMock()
        config = AgentConfig(model="gpt-4", provider=provider)
        assert config.capture_content is False
