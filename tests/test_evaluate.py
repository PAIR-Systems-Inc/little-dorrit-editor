"""Tests for the evaluation module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import TypeAdapter
from rich.console import Console

from little_dorrit_editor.evaluate import (
    LLMJudge,
    calculate_metrics,
    match_edits,
)
from little_dorrit_editor.types import EditAnnotation

# Patch rich.console.Console to avoid output during tests
@pytest.fixture(autouse=True)
def mock_console():
    with patch("rich.console.Console.print") as mock_print:
        yield mock_print


def test_match_edits_exact_match():
    """Test matching when predictions exactly match ground truth."""
    # Create sample annotations
    ground_truth = EditAnnotation.model_validate({
        "image": "test.png",
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "type": "insertion",
                "original_text": "",
                "corrected_text": "test",
                "line_number": 10
            }
        ]
    })
    
    prediction = EditAnnotation.model_validate({
        "image": "test.png",
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "type": "insertion",
                "original_text": "",
                "corrected_text": "test",
                "line_number": 10
            }
        ]
    })
    
    # Match edits
    true_positives, false_positives, false_negatives = match_edits(
        ground_truth, prediction
    )
    
    # Check results
    assert len(true_positives) == 1
    assert len(false_positives) == 0
    assert len(false_negatives) == 0
    
    gt_edit, pred_edit = true_positives[0]
    assert gt_edit["type"] == "insertion"
    assert gt_edit["line_number"] == 10
    assert pred_edit["corrected_text"] == "test"


def test_match_edits_no_match():
    """Test matching when predictions don't match ground truth at all."""
    # Create sample annotations
    ground_truth = EditAnnotation.model_validate({
        "image": "test.png",
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "type": "insertion",
                "original_text": "",
                "corrected_text": "test",
                "line_number": 10
            }
        ]
    })
    
    prediction = EditAnnotation.model_validate({
        "image": "test.png",
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "type": "deletion",  # Different edit type
                "original_text": "wrong",
                "corrected_text": "",
                "line_number": 50  # Different line number
            }
        ]
    })
    
    # Match edits
    true_positives, false_positives, false_negatives = match_edits(
        ground_truth, prediction
    )
    
    # Check results
    assert len(true_positives) == 0
    assert len(false_positives) == 1
    assert len(false_negatives) == 1
    
    assert false_positives[0]["type"] == "deletion"
    assert false_negatives[0]["type"] == "insertion"


def test_match_edits_partial_match():
    """Test matching when some predictions match ground truth but not all."""
    # Create sample annotations
    ground_truth = EditAnnotation.model_validate({
        "image": "test.png",
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "type": "insertion",
                "original_text": "",
                "corrected_text": "test1",
                "line_number": 10
            },
            {
                "type": "deletion",
                "original_text": "test2",
                "corrected_text": "",
                "line_number": 20
            }
        ]
    })
    
    prediction = EditAnnotation.model_validate({
        "image": "test.png",
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "type": "insertion",
                "original_text": "",
                "corrected_text": "test1",
                "line_number": 10
            },
            {
                "type": "replacement",  # Different from ground truth
                "original_text": "test3",
                "corrected_text": "test4",
                "line_number": 30
            }
        ]
    })
    
    # Match edits
    true_positives, false_positives, false_negatives = match_edits(
        ground_truth, prediction
    )
    
    # Check results
    assert len(true_positives) == 1
    assert len(false_positives) == 1
    assert len(false_negatives) == 1
    
    gt_edit, pred_edit = true_positives[0]
    assert gt_edit["type"] == "insertion"
    assert pred_edit["corrected_text"] == "test1"
    
    assert false_positives[0]["type"] == "replacement"
    assert false_negatives[0]["type"] == "deletion"


def test_calculate_metrics_perfect():
    """Test metric calculation with perfect predictions."""
    # Create sample data
    true_positives = [
        ({"type": "insertion"}, {"type": "insertion"}),
        ({"type": "deletion"}, {"type": "deletion"})
    ]
    false_positives = []
    false_negatives = []
    judgments = [{"is_correct": True, "score": 1.0}, {"is_correct": True, "score": 1.0}]
    
    # Calculate metrics
    metrics = calculate_metrics(
        true_positives, false_positives, false_negatives, judgments
    )
    
    # Check results
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["correct_count"] == 2
    assert metrics["total_ground_truth"] == 2
    assert metrics["total_predicted"] == 2


def test_calculate_metrics_zero():
    """Test metric calculation with zero predictions."""
    # Create sample data with empty results
    true_positives = []
    false_positives = []
    false_negatives = [{"type": "insertion"}]
    judgments = []
    
    # Calculate metrics
    metrics = calculate_metrics(
        true_positives, false_positives, false_negatives, judgments
    )
    
    # Check results
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["correct_count"] == 0
    assert metrics["total_ground_truth"] == 1
    assert metrics["total_predicted"] == 0


def test_calculate_metrics_mixed():
    """Test metric calculation with mixed results."""
    # Create sample data
    true_positives = [
        ({"type": "insertion"}, {"type": "insertion"}),
        ({"type": "deletion"}, {"type": "deletion"}),
        ({"type": "replacement"}, {"type": "replacement"})
    ]
    false_positives = [{"type": "punctuation"}]
    false_negatives = [{"type": "capitalization"}]
    judgments = [{"is_correct": True, "score": 1.0}, {"is_correct": False, "score": 0.0}, {"is_correct": True, "score": 1.0}]
    
    # Calculate metrics
    metrics = calculate_metrics(
        true_positives, false_positives, false_negatives, judgments
    )
    
    # Check results - 2 out of 3 true positives are correct according to LLM
    # 2 correct out of 4 predictions (2 + 1 false positive) = 0.5 precision
    # 2 correct out of 4 ground truth (2 + 1 false negative) = 0.5 recall
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1_score"] == 0.5
    assert metrics["correct_count"] == 2
    assert metrics["total_ground_truth"] == 4
    assert metrics["total_predicted"] == 4


@patch("openai.Client")
@patch("little_dorrit_editor.evaluate.get_model")
def test_llm_judge(mock_get_model, mock_client):
    """Test the LLM judge evaluation."""
    # Mock the model config
    mock_model_config = MagicMock()
    mock_model_config.api_key = "test_key"
    mock_model_config.endpoint = "https://api.test.com"
    mock_model_config.model_name = "test_model"
    mock_model_config.logical_name = "Test Model"
    mock_get_model.return_value = mock_model_config
    
    # Mock the OpenAI client
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    mock_message.content = '{"is_correct": true, "reasoning": "The prediction matches the ground truth"}'
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.return_value = mock_completion
    mock_client.return_value = mock_client_instance
    
    # Create the judge
    judge = LLMJudge(model_id="test_model")
    
    # Test evaluation
    ground_truth_edit = {
        "type": "insertion",
        "original_text": "",
        "corrected_text": "test",
        "line_number": 10
    }
    
    predicted_edit = {
        "type": "insertion",
        "original_text": "",
        "corrected_text": "test",
        "line_number": 10
    }
    
    result = judge.evaluate_edit(ground_truth_edit, predicted_edit)
    
    # Check that the client was called with the right arguments
    mock_client_instance.chat.completions.create.assert_called_once()
    call_args = mock_client_instance.chat.completions.create.call_args[1]
    assert call_args["model"] == "test_model"  # Should use model_name from config
    assert len(call_args["messages"]) == 2
    assert call_args["response_format"] == {"type": "json_object"}
    
    # Check the result
    assert result["is_correct"] is True
    assert result["reasoning"] == "The prediction matches the ground truth"


def test_match_edits_missing_line_number():
    """Test matching when some predictions are missing line numbers."""
    # Create sample annotations with updated schema
    ground_truth = EditAnnotation(
        image="test.png",
        page_number=1,
        source="Little Dorrit",
        edits=[
            {
                "type": "insertion",
                "original_text": "original",
                "corrected_text": "corrected",
                "line_number": 10
            }
        ]
    )
    
    # Create a prediction with one edit missing a line number
    prediction = EditAnnotation(
        image="test.png",
        page_number=1,
        source="Little Dorrit",
        edits=[
            {
                "type": "insertion",
                "original_text": "original",
                "corrected_text": "corrected",
                "line_number": 10
            },
            {
                "type": "deletion",
                "original_text": "to be deleted",
                "corrected_text": "",
                # line_number deliberately omitted
            }
        ]
    )
    
    # Match edits
    true_positives, false_positives, false_negatives = match_edits(
        ground_truth, prediction
    )
    
    # Check results - should only match the edit with line number
    assert len(true_positives) == 1
    assert len(false_positives) == 0
    assert len(false_negatives) == 0
    
    # The missing line number edit should be filtered out completely
    assert all("line_number" in edit for edit in false_positives)