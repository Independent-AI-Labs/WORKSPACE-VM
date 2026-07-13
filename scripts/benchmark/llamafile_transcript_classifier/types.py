"""Shared JSON-compatible types for benchmark payloads."""

from __future__ import annotations

from typing import TypedDict

TOKENS_PER_K = 1024
CLASSIFICATION_CATEGORY_COUNT = 7
HTTP_STATUS_OK = 200
HTTP_STATUS_NOT_IMPLEMENTED = 501
DEFAULT_MAX_CONTEXT_TOKENS = 32768
BUCKET_THRESHOLD_LARGE = 65536
BUCKET_THRESHOLD_MEDIUM = 16384

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonMap = dict[str, JsonValue]

NA_CELL = "n/a"


class CategoryEntry(TypedDict, total=False):
    id: str
    description: str


def ctx_label(tokens: int) -> str:
    if tokens < TOKENS_PER_K:
        return f"{tokens}"
    return f"{tokens // TOKENS_PER_K}K"
