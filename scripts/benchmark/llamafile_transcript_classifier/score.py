"""Score YAML category classification responses."""

from __future__ import annotations

import re
from typing import NamedTuple

import yaml

from scripts.benchmark.llamafile_transcript_classifier.types import JsonValue


class ScoreResult(NamedTuple):
    passed: bool
    yaml_ok: bool
    categories_ok: bool
    range_ok: bool
    parsed_scores: dict[str, float]
    notes: str


def _extract_yaml_block(text: str) -> str:
    fenced = re.search(
        r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE
    )
    if fenced:
        return fenced.group(1).strip()
    start = text.find("scores:")
    if start >= 0:
        return text[start:].strip()
    return text.strip()


def _coerce_score(value: JsonValue) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", stripped):
            return float(stripped)
        return None
    return None


def parse_classification_yaml(
    response: str,
    category_ids: list[str],
) -> tuple[dict[str, float], list[str]]:
    """Parse category scores from model YAML output."""
    errors: list[str] = []
    raw = _extract_yaml_block(response)
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return {}, [f"yaml parse error: {exc}"]

    if not isinstance(parsed, dict):
        return {}, ["top-level YAML must be a mapping"]

    scores_obj = parsed.get("scores", parsed)
    if not isinstance(scores_obj, dict):
        return {}, ["scores section must be a mapping"]

    parsed_scores: dict[str, float] = {}
    for cat_id in category_ids:
        if cat_id not in scores_obj:
            errors.append(f"missing category: {cat_id}")
            continue
        value = _coerce_score(scores_obj[cat_id])
        if value is None:
            errors.append(f"non-numeric score for {cat_id}")
            continue
        if value < -1.0 or value > 1.0:
            errors.append(f"out of range for {cat_id}: {value}")
            continue
        parsed_scores[cat_id] = value

    extra = sorted(set(scores_obj) - set(category_ids))
    if extra:
        errors.append(f"unexpected categories: {', '.join(extra)}")

    return parsed_scores, errors


def score_answer(
    response: str,
    category_ids: list[str],
    expected_ranges: dict[str, dict[str, float]] | None = None,
) -> ScoreResult:
    """Grade a YAML classification response."""
    parsed_scores, errors = parse_classification_yaml(response, category_ids)
    yaml_ok = not any("yaml parse error" in e for e in errors)
    categories_ok = len(parsed_scores) == len(category_ids)

    range_ok = True
    range_errors: list[str] = []
    if expected_ranges:
        for cat_id, bounds in expected_ranges.items():
            if cat_id not in parsed_scores:
                continue
            value = parsed_scores[cat_id]
            low = float(bounds.get("min", -1.0))
            high = float(bounds.get("max", 1.0))
            if value < low or value > high:
                range_ok = False
                range_errors.append(f"{cat_id} expected [{low}, {high}] got {value}")

    passed = yaml_ok and categories_ok and range_ok and not errors
    notes_parts = list(errors) + range_errors
    return ScoreResult(
        passed=passed,
        yaml_ok=yaml_ok,
        categories_ok=categories_ok,
        range_ok=range_ok,
        parsed_scores=parsed_scores,
        notes="; ".join(notes_parts) if notes_parts else "ok",
    )
