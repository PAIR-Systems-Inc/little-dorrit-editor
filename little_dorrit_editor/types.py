"""Type definitions for the Little Dorrit Editor project."""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class EditType(str, Enum):
    """Types of editorial changes."""

    INSERTION = "insertion"
    DELETION = "deletion"
    REPLACEMENT = "replacement"
    PUNCTUATION = "punctuation"
    CAPITALIZATION = "capitalization"
    REORDERING = "reordering"


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


class EvaluationResult(BaseModel):
    """Results from evaluating a model's predictions against ground truth."""

    model_name: str = Field(..., description="Name of the evaluated model")
    precision: float = Field(..., description="Precision score")
    recall: float = Field(..., description="Recall score")
    f1_score: float = Field(..., description="F1 score")
    date: str = Field(..., description="Evaluation date (ISO 8601)")
    details: dict = Field(
        ..., description="Detailed results including per-edit-type metrics"
    )