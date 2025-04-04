"""Tests for the evaluation module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import TypeAdapter

from little_dorrit_editor.evaluate import (
    LLMJudge,
    calculate_metrics,
    match_edits,
)
from little_dorrit_editor.types import EditAnnotation


def test_match_edits_exact_match():
    """Test matching when predictions exactly match ground truth."""
    # Create sample annotations
    ground_truth = EditAnnotation.model_validate({
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "edit_type": "insertion",
                "location": {
                    "start_idx": 10,
                    "end_idx": 10,
                    "text": ""
                },
                "edited_text": "test"
            }
        ]
    })
    
    prediction = EditAnnotation.model_validate({
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "edit_type": "insertion",
                "location": {
                    "start_idx": 10,
                    "end_idx": 10,
                    "text": ""
                },
                "edited_text": "test"
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
    assert gt_edit["edit_type"] == "insertion"
    assert gt_edit["location"]["start_idx"] == 10
    assert pred_edit["edited_text"] == "test"


def test_match_edits_no_match():
    """Test matching when predictions don't match ground truth at all."""
    # Create sample annotations
    ground_truth = EditAnnotation.model_validate({
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "edit_type": "insertion",
                "location": {
                    "start_idx": 10,
                    "end_idx": 10,
                    "text": ""
                },
                "edited_text": "test"
            }
        ]
    })
    
    prediction = EditAnnotation.model_validate({
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "edit_type": "deletion",  # Different edit type
                "location": {
                    "start_idx": 50,  # Different location
                    "end_idx": 55,
                    "text": "wrong"
                }
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
    
    assert false_positives[0]["edit_type"] == "deletion"
    assert false_negatives[0]["edit_type"] == "insertion"


def test_match_edits_partial_match():
    """Test matching when some predictions match ground truth but not all."""
    # Create sample annotations
    ground_truth = EditAnnotation.model_validate({
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "edit_type": "insertion",
                "location": {
                    "start_idx": 10,
                    "end_idx": 10,
                    "text": ""
                },
                "edited_text": "test1"
            },
            {
                "edit_type": "deletion",
                "location": {
                    "start_idx": 20,
                    "end_idx": 25,
                    "text": "test2"
                }
            }
        ]
    })
    
    prediction = EditAnnotation.model_validate({
        "page_number": 1,
        "source": "Little Dorrit",
        "edits": [
            {
                "edit_type": "insertion",
                "location": {
                    "start_idx": 10,
                    "end_idx": 10,
                    "text": ""
                },
                "edited_text": "test1"
            },
            {
                "edit_type": "replacement",  # Different from ground truth
                "location": {
                    "start_idx": 30,
                    "end_idx": 35,
                    "text": "test3"
                },
                "edited_text": "test4"
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
    assert gt_edit["edit_type"] == "insertion"
    assert pred_edit["edited_text"] == "test1"
    
    assert false_positives[0]["edit_type"] == "replacement"
    assert false_negatives[0]["edit_type"] == "deletion"


def test_calculate_metrics_perfect():
    """Test metric calculation with perfect predictions."""
    # Create sample data
    true_positives = [
        ({"edit_type": "insertion"}, {"edit_type": "insertion"}),
        ({"edit_type": "deletion"}, {"edit_type": "deletion"})
    ]
    false_positives = []
    false_negatives = []
    judgments = [{"is_correct": True}, {"is_correct": True}]
    
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
    false_negatives = [{"edit_type": "insertion"}]
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
        ({"edit_type": "insertion"}, {"edit_type": "insertion"}),
        ({"edit_type": "deletion"}, {"edit_type": "deletion"}),
        ({"edit_type": "replacement"}, {"edit_type": "replacement"})
    ]
    false_positives = [{"edit_type": "punctuation"}]
    false_negatives = [{"edit_type": "capitalization"}]
    judgments = [{"is_correct": True}, {"is_correct": False}, {"is_correct": True}]
    
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
def test_llm_judge(mock_client):
    """Test the LLM judge evaluation."""
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
    judge = LLMJudge(api_key="test_key", model="test_model")
    
    # Test evaluation
    ground_truth_edit = {
        "edit_type": "insertion",
        "location": {
            "start_idx": 10,
            "end_idx": 10,
            "text": ""
        },
        "edited_text": "test"
    }
    
    predicted_edit = {
        "edit_type": "insertion",
        "location": {
            "start_idx": 10,
            "end_idx": 10,
            "text": ""
        },
        "edited_text": "test"
    }
    
    result = judge.evaluate_edit(ground_truth_edit, predicted_edit)
    
    # Check that the client was called with the right arguments
    mock_client_instance.chat.completions.create.assert_called_once()
    call_args = mock_client_instance.chat.completions.create.call_args[1]
    assert call_args["model"] == "test_model"
    assert len(call_args["messages"]) == 2
    assert call_args["response_format"] == {"type": "json_object"}
    
    # Check the result
    assert result["is_correct"] is True
    assert result["reasoning"] == "The prediction matches the ground truth"