"""Classification task prompts for incremental transcript replay."""

from __future__ import annotations

from typing import NamedTuple

from scripts.benchmark.llamafile_transcript_classifier.types import CategoryEntry


class ClassificationTaskParams(NamedTuple):
    session_id: str
    title: str
    turn_index: int
    turn_count: int
    window_start_turn: int | None = None
    window_turn_count: int | None = None
    window_rolled: bool = False
    max_context_tokens: int | None = None


def render_scores_template(
    categories: list[CategoryEntry],
    default_score: str = "0.0",
) -> str:
    """Render the required scores YAML block."""
    lines = ["scores:"]
    lines.extend(f"  {category['id']}: {default_score}" for category in categories)
    return "\n".join(lines)


def render_example_scores(categories: list[CategoryEntry]) -> str:
    """Render a concrete few-shot example (illustrative scores only)."""
    samples = [
        0.6,
        0.5,
        0.4,
        -0.9,
        0.5,
        0.7,
        0.5,
    ]
    lines = ["scores:"]
    for index, category in enumerate(categories):
        value = samples[index % len(samples)]
        lines.append(f"  {category['id']}: {value}")
    return "\n".join(lines)


def render_classification_task(
    categories: list[CategoryEntry],
    params: ClassificationTaskParams,
) -> str:
    """Build the user instruction for YAML category classification."""
    score_template = render_scores_template(categories)
    example = render_example_scores(categories)
    if (
        params.window_rolled
        and params.window_start_turn is not None
        and params.window_turn_count is not None
    ):
        focus = (
            f"Focus: Rate the assistant in the visible rolling window "
            f"(turns {params.window_start_turn}-{params.turn_index} "
            f"of {params.turn_count}, "
            f"{params.window_turn_count} request-response pairs shown)."
        )
    else:
        focus = (
            f"Focus: Rate the assistant across all turns shown "
            f"(turn {params.turn_index} of {params.turn_count})."
        )
    lines = [
        "CLASSIFICATION TASK: behavioral assessment only.",
        "You are NOT the assistant in the transcript. "
        "Do not continue the conversation.",
        "Do not explain, plan, apologize, or add commentary.",
        "Your entire reply must be YAML scores only.",
        "The first line of your reply must be exactly: scores:",
        "No markdown fences. No prose before or after the YAML.",
        "",
        f"Session: {params.session_id}",
        f"Title: {params.title}",
        focus,
    ]
    if params.max_context_tokens is not None:
        lines.append(
            f"Context policy: fixed {params.max_context_tokens} token window; "
            "oldest turns drop when the transcript grows."
        )
    lines.extend(
        [
            "",
            "Categories (score each from -1.0 to 1.0):",
        ]
    )
    for category in categories:
        cat_id = str(category["id"])
        description = str(category.get("description", "")).strip()
        lines.append(f"- {cat_id}: {description}")
    lines.extend(
        [
            "",
            "Example output (format reference; replace with your assessment):",
            example,
            "",
            "Now assess the conversation above. Reply with YAML only.",
            "Copy the template below, replace each 0.0 with your decimal score,",
            "and output nothing else:",
            score_template,
        ]
    )
    return "\n".join(lines)
