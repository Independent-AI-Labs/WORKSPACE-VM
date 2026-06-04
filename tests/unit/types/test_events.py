"""Unit tests for workspace.types.events models."""

import time

from workspace.types.api import ProviderMetadata, StreamMetadata
from workspace.types.events import (
    StreamEvent,
    StreamEventPayload,
    StreamEventType,
)

_EVENT_TYPE_COUNT = 4


class TestStreamEventType:
    def test_members(self) -> None:
        assert StreamEventType.CHUNK == "chunk"
        assert StreamEventType.METADATA == "metadata"
        assert StreamEventType.ERROR == "error"
        assert StreamEventType.COMPLETE == "complete"

    def test_iteration(self) -> None:
        members = list(StreamEventType)
        assert len(members) == _EVENT_TYPE_COUNT

    def test_string_value(self) -> None:
        assert StreamEventType.CHUNK.value == "chunk"


class TestStreamEvent:
    def test_construction(self) -> None:
        event = StreamEvent(type=StreamEventType.CHUNK, data="hello")
        assert event.type == StreamEventType.CHUNK
        assert event.data == "hello"
        assert isinstance(event.timestamp, float)

    def test_timestamp_defaults_to_now(self) -> None:
        before = time.time()
        event = StreamEvent(type=StreamEventType.CHUNK, data="x")
        after = time.time()
        before_ms = int(before * 1000)
        after_ms = int(after * 1000)
        event_ms = int(event.timestamp * 1000)
        assert before_ms <= event_ms <= after_ms + 1

    def test_chunk_factory(self) -> None:
        event = StreamEvent.chunk("content here")
        assert event.type == StreamEventType.CHUNK
        assert event.data == "content here"

    def test_metadata_factory(self) -> None:
        meta = StreamMetadata()
        event = StreamEvent.metadata(meta)
        assert event.type == StreamEventType.METADATA
        assert event.data is meta

    def test_error_factory(self) -> None:
        event = StreamEvent.error("something went wrong")
        assert event.type == StreamEventType.ERROR
        assert event.data == "something went wrong"

    def test_complete_factory(self) -> None:
        meta = ProviderMetadata(model="gpt-4")
        event = StreamEvent.complete("output text", meta)
        assert event.type == StreamEventType.COMPLETE
        assert event.data.output == "output text"
        assert event.data.metadata is meta

    def test_str_data(self) -> None:
        event = StreamEvent(type=StreamEventType.ERROR, data="err msg")
        assert isinstance(event.data, str)

    def test_payload_type_accepts_string(self) -> None:
        val: StreamEventPayload = "string data"
        assert isinstance(val, str)

    def test_missing_timestamp_assigns_default(self) -> None:
        before = time.time()
        event = StreamEvent(type=StreamEventType.CHUNK, data="x")
        after = time.time()
        assert before <= event.timestamp <= after + 0.1
