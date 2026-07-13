"""HTTP client for llamafile server benchmark metrics."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import NamedTuple

from scripts.benchmark.llamafile_transcript_classifier.types import (
    HTTP_STATUS_NOT_IMPLEMENTED,
    HTTP_STATUS_OK,
    JsonMap,
)


class CompletionMetrics(NamedTuple):
    response_text: str
    ttft_ms: float | None
    total_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    tokens_per_second: float | None
    cache_n: int | None
    prompt_n: int | None


class CompletionRequest(NamedTuple):
    base_url: str
    messages: list[dict[str, str]]
    max_tokens: int
    temperature: float
    timeout_s: float = 3600.0
    id_slot: int = 0
    cache_prompt: bool = True
    timings_per_token: bool = True


class StreamParseState:
    """Mutable accumulator while parsing a streaming chat completion."""

    __slots__ = (
        "cache_n",
        "completion_tokens",
        "parts",
        "prompt_n",
        "prompt_tokens",
        "total_tokens",
        "ttft_ms",
    )

    def __init__(self) -> None:
        self.ttft_ms: float | None = None
        self.parts: list[str] = []
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.total_tokens: int | None = None
        self.cache_n: int | None = None
        self.prompt_n: int | None = None


def _post_json(url: str, payload: JsonMap, timeout_s: float) -> JsonMap:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        msg = f"unexpected JSON response: {parsed!r}"
        raise TypeError(msg)
    return parsed


def health_ok(base_url: str, timeout_s: float = 10.0) -> bool:
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return resp.status == HTTP_STATUS_OK
    except (urllib.error.URLError, TimeoutError):
        return False


class SlotEraseResult(NamedTuple):
    supported: bool
    erased: bool
    detail: str


def erase_slot(base_url: str, slot_id: int, timeout_s: float = 30.0) -> SlotEraseResult:
    """Erase KV cache for a pinned slot before starting a new session replay."""
    url = f"{base_url.rstrip('/')}/slots/{slot_id}?action=erase"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == HTTP_STATUS_NOT_IMPLEMENTED:
            return SlotEraseResult(
                supported=False,
                erased=False,
                detail="slot erase not supported (start server with --slot-save-path)",
            )
        raise
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        msg = f"unexpected slot erase response: {parsed!r}"
        raise TypeError(msg)
    return SlotEraseResult(supported=True, erased=True, detail=json.dumps(parsed))


def count_input_tokens(
    base_url: str,
    messages: list[dict[str, str]],
    timeout_s: float = 120.0,
) -> int:
    url = f"{base_url.rstrip('/')}/v1/chat/completions/input_tokens"
    result = _post_json(url, {"messages": messages}, timeout_s)
    tokens = result.get("input_tokens")
    if not isinstance(tokens, int):
        msg = f"unexpected token count response: {result!r}"
        raise TypeError(msg)
    return tokens


def _append_stream_content(
    content: object,
    started: float,
    state: StreamParseState,
) -> None:
    if not content:
        return
    if state.ttft_ms is None:
        state.ttft_ms = (time.perf_counter() - started) * 1000.0
    state.parts.append(str(content))


def _apply_choice_delta(
    choice: object,
    started: float,
    state: StreamParseState,
) -> None:
    if not isinstance(choice, dict):
        return
    delta = choice.get("delta") or {}
    if isinstance(delta, dict):
        _append_stream_content(delta.get("content"), started, state)


def _apply_usage_stats(usage: object, state: StreamParseState) -> None:
    if not isinstance(usage, dict):
        return
    prompt_tokens = usage.get("prompt_tokens")
    if isinstance(prompt_tokens, int):
        state.prompt_tokens = prompt_tokens
    completion_tokens = usage.get("completion_tokens")
    if isinstance(completion_tokens, int):
        state.completion_tokens = completion_tokens
    total_tokens = usage.get("total_tokens")
    if isinstance(total_tokens, int):
        state.total_tokens = total_tokens


def _apply_timing_stats(timings: object, state: StreamParseState) -> None:
    if not isinstance(timings, dict):
        return
    cache_n = timings.get("cache_n")
    if isinstance(cache_n, int):
        state.cache_n = cache_n
    prompt_n = timings.get("prompt_n")
    if isinstance(prompt_n, int):
        state.prompt_n = prompt_n


def _apply_stream_event(
    event: JsonMap,
    started: float,
    state: StreamParseState,
) -> None:
    choices = event.get("choices") or []
    if isinstance(choices, list) and choices:
        _apply_choice_delta(choices[0], started, state)
    _apply_usage_stats(event.get("usage"), state)
    _apply_timing_stats(event.get("timings"), state)


def stream_chat_completion(request: CompletionRequest) -> CompletionMetrics:
    url = f"{request.base_url.rstrip('/')}/v1/chat/completions"
    payload: JsonMap = {
        "model": "benchmark",
        "messages": request.messages,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
        "id_slot": request.id_slot,
        "cache_prompt": request.cache_prompt,
        "timings_per_token": request.timings_per_token,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    state = StreamParseState()

    with urllib.request.urlopen(req, timeout=request.timeout_s) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            event = json.loads(chunk)
            if isinstance(event, dict):
                _apply_stream_event(event, started, state)

    total_ms = (time.perf_counter() - started) * 1000.0
    text = "".join(state.parts)
    completion_tokens = state.completion_tokens
    tps: float | None = None
    if isinstance(completion_tokens, int) and total_ms > 0:
        tps = completion_tokens / (total_ms / 1000.0)

    return CompletionMetrics(
        response_text=text,
        ttft_ms=state.ttft_ms,
        total_ms=total_ms,
        prompt_tokens=state.prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=state.total_tokens,
        tokens_per_second=tps,
        cache_n=state.cache_n,
        prompt_n=state.prompt_n,
    )


def probe_cache_reuse(
    base_url: str,
    id_slot: int = 0,
    timeout_s: float = 120.0,
) -> JsonMap:
    """Verify prompt cache reuse via two incremental requests on one slot."""
    erase_result = erase_slot(base_url, id_slot, timeout_s=timeout_s)
    prefix = [
        {"role": "system", "content": "cache probe"},
        {"role": "user", "content": "prefix " * 80},
        {"role": "assistant", "content": "acknowledged"},
    ]
    first = stream_chat_completion(
        CompletionRequest(
            base_url=base_url,
            messages=[*prefix, {"role": "user", "content": "classify: ok"}],
            max_tokens=4,
            temperature=0.0,
            timeout_s=timeout_s,
            id_slot=id_slot,
            cache_prompt=True,
        )
    )
    second = stream_chat_completion(
        CompletionRequest(
            base_url=base_url,
            messages=[
                *prefix,
                {"role": "user", "content": "follow-up question"},
                {"role": "assistant", "content": "follow-up answer"},
                {"role": "user", "content": "classify: ok"},
            ],
            max_tokens=4,
            temperature=0.0,
            timeout_s=timeout_s,
            id_slot=id_slot,
            cache_prompt=True,
        )
    )
    cache_working = (second.cache_n or 0) > 0
    return {
        "id_slot": id_slot,
        "slot_erase_supported": erase_result.supported,
        "slot_erase_detail": erase_result.detail,
        "first_prompt_tokens": first.prompt_tokens,
        "second_prompt_tokens": second.prompt_tokens,
        "second_cache_n": second.cache_n,
        "second_prompt_n": second.prompt_n,
        "cache_working": cache_working,
    }
