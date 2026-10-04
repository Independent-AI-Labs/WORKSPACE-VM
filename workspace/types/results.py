"""Result types for function return values.

Provides NamedTuples that support tuple unpacking while adding named field access.
"""

from selectors import SelectorKey
from typing import NamedTuple, TypedDict

from .api import ProviderMetadata, StreamMetadata


class ParseResult(NamedTuple):
    """Result from parsing a stream message."""

    text: str
    metadata: StreamMetadata | None


class ProviderResult(NamedTuple):
    """Result from provider execution."""

    output: str
    metadata: ProviderMetadata | None


class SafetyCheckResult(NamedTuple):
    """Result from a safety check."""

    is_safe: bool
    message: str


class ReadLineResult(NamedTuple):
    """Result from reading a streaming line."""

    line: str | None
    is_complete: bool


class BinaryCheckResult(NamedTuple):
    """Result from checking if a binary exists."""

    exists: bool
    version: str | None


class ConfigDefaults(NamedTuple):
    """Default configuration values."""

    provider: str
    model: str


class FormattedPrefix(NamedTuple):
    """Prefix with formatting and visible width."""

    formatted: str
    visible: str


class GroupRange(NamedTuple):
    """Range information for a dialog group."""

    header_idx: int
    start: int
    end: int


class FileViolation(NamedTuple):
    """A file that violates a policy."""

    filepath: str
    line_count: int


class TempFileEntry(NamedTuple):
    """A temporary file with its size."""

    path: str
    size_bytes: int


class ComponentStatusEntry(NamedTuple):
    """Status entry for a single component."""

    name: str
    installed: bool
    version: str | None
    description: str
    category: str = ""


class SelectorEvent(NamedTuple):
    """A selector event with key and mask."""

    key: SelectorKey
    mask: int


class DeleteResult(NamedTuple):
    """Result from deleting items."""

    deleted: int
    errors: int


class ScanResult(NamedTuple):
    """Result from scanning for files."""

    found: list[str]
    large: list[str]


class CharWithOrdinal(NamedTuple):
    """Character with its ordinal value."""

    char: str
    ordinal: int


class ModeHandler(NamedTuple):
    """Mode handler with condition and handler function."""

    condition: str | bool | None
    handler: object  # Callable[[], int]


class KeyHandleResult(NamedTuple):
    """Result from handling a key press in selection dialog."""

    should_continue: bool
    result: object  # SelectableItem | SelectableItemDict | list | None


class NamedComponentStatus(NamedTuple):
    """Component status paired with its name for collection use."""

    name: str
    installed: bool
    version: str | None
    path: str | None


class InstallationResult(TypedDict):
    """Result of component installation."""

    component_name: str
    success: bool
    error: str | None
