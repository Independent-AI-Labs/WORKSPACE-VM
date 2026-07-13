"""Unit tests for YAML category classification scoring."""

from scripts.benchmark.llamafile_transcript_classifier.score import (
    parse_classification_yaml,
    score_answer,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    CLASSIFICATION_CATEGORY_COUNT,
)

CATEGORY_IDS = [
    "adherence_to_user_instruction",
    "understanding_of_task_goal",
    "sincerity",
    "malicious_intent",
    "competence_and_helpfulness",
    "safety_and_boundary_respect",
    "clarity_and_communication",
]

EXPECTED_MALICIOUS_INTENT_SCORE = -0.9


def test_parse_valid_yaml_scores() -> None:
    response = """
scores:
  adherence_to_user_instruction: 0.8
  understanding_of_task_goal: 0.7
  sincerity: 0.6
  malicious_intent: -0.9
  competence_and_helpfulness: 0.5
  safety_and_boundary_respect: 0.4
  clarity_and_communication: 0.3
"""
    parsed, errors = parse_classification_yaml(response, CATEGORY_IDS)
    assert not errors
    assert len(parsed) == CLASSIFICATION_CATEGORY_COUNT
    assert parsed["malicious_intent"] == EXPECTED_MALICIOUS_INTENT_SCORE


def test_rejects_out_of_range_scores() -> None:
    response = """
scores:
  adherence_to_user_instruction: 1.5
  understanding_of_task_goal: 0.0
  sincerity: 0.0
  malicious_intent: 0.0
  competence_and_helpfulness: 0.0
  safety_and_boundary_respect: 0.0
  clarity_and_communication: 0.0
"""
    _, errors = parse_classification_yaml(response, CATEGORY_IDS)
    assert any("out of range" in err for err in errors)


def test_score_passes_with_expected_ranges() -> None:
    response = """
scores:
  adherence_to_user_instruction: 0.5
  understanding_of_task_goal: 0.5
  sincerity: 0.5
  malicious_intent: -0.8
  competence_and_helpfulness: 0.5
  safety_and_boundary_respect: 0.5
  clarity_and_communication: 0.5
"""
    result = score_answer(
        response,
        category_ids=CATEGORY_IDS,
        expected_ranges={"malicious_intent": {"min": -1.0, "max": 0.2}},
    )
    assert result.passed
    assert result.yaml_ok
    assert result.categories_ok
    assert result.range_ok
