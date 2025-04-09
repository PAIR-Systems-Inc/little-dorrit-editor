"""Type definitions for the Little Dorrit Editor project."""

from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class EditType(str, Enum):
    """Types of editorial changes."""

    INSERTION = "insertion"
    DELETION = "deletion"
    REPLACEMENT = "replacement"
    PUNCTUATION = "punctuation"
    CAPITALIZATION = "capitalization"
    REORDERING = "reordering"
    ITALICIZE = "italicize"


class EditMatch(BaseModel):
    """Represents a single edit evaluation/match result."""

    # Edit matching information
    observed_edit_num: Optional[int] = Field(None, description="Index of the observed edit in model's prediction")
    expected_edit_num: Optional[int] = Field(None, description="Index of the expected edit in ground truth")

    # Evaluation scores - These maintain the invariant: tp + fp + fn = 1.0
    tp: float = Field(..., description="True positive score (1.0 for perfect match, reduced by line_number_penalty)")
    fp: float = Field(..., description="False positive score (increases as tp decreases)")
    fn: float = Field(..., description="False negative score (increases as tp decreases)")

    # Edit content (for matches and false positives)
    type: Optional[EditType] = Field(None, description="Type of edit operation")
    original_text: Optional[str] = Field(None, description="The original text observed")
    corrected_text: Optional[str] = Field(None, description="The corrected text observed")

    # Line number evaluation
    observed_line_number: Optional[int] = Field(None, description="Line number in the prediction")
    line_diff: Optional[int] = Field(None, description="Difference between predicted and expected line numbers")
    line_number_penalty: float = Field(0.0, description="Penalty applied for line number differences (reduces tp)")

    # Judgment information
    judgement: Optional[str] = Field(None, description="Explanation of the evaluation decision")


class EvaluationResult(BaseModel):
    """Results from evaluating a model's predictions against ground truth."""

    # Model identification
    model_name: str = Field(..., description="Name of the evaluated model")
    date: str = Field(..., description="Evaluation date (ISO 8601)")
    annotator: Optional[str] = Field(None, description="Name of the model/annotator that made the prediction")
    annotation_date: Optional[str] = Field(None, description="Date when the prediction was made (ISO 8601)")

    # Detailed results - list of edit matches
    details: List[EditMatch] = Field(..., description="Detailed results for each edit match")


# DEPRECATED: These models are kept temporarily for compatibility
class EditOperation(BaseModel):
    """An editorial operation on text."""

    type: str = Field(..., description="Type of edit operation")
    original_text: str = Field(..., description="The original text")
    corrected_text: str = Field(..., description="The corrected text")
    line_number: Optional[int] = Field(None, description="Line number in the page (0 for titles, 1+ for body text)")
    page: Optional[str] = Field(None, description="Page identifier (e.g., filename)")
    confidence: Optional[float] = Field(None, description="Model's confidence score")
    notes: Optional[str] = Field(None, description="Additional notes about the edit")


class EditAnnotation(BaseModel):
    """A collection of edits for a specific page."""

    image: str = Field(..., description="Image filename")
    page_number: int = Field(..., description="Page number in the source document")
    source: Literal["Little Dorrit"] = Field(
        "Little Dorrit", description="Source document title"
    )
    edits: list[EditOperation] = Field(..., description="List of edit operations")
    annotator: Optional[str] = Field(None, description="Name of the human annotator")
    annotation_date: Optional[str] = Field(
        None, description="Date of annotation (ISO 8601)"
    )
    verified: Optional[bool] = Field(
        None, description="Whether the annotation has been verified"
    )
    error: Optional[str] = Field(
        None, description="Error message if prediction generation failed"
    )
    raw_response: Optional[str] = Field(
        None, description="Raw model response excerpt for debugging (if error occurred)"
    )