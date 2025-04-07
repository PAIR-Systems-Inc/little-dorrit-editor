"""Evaluation logic for the Little Dorrit Editor benchmark."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import openai
from rich.console import Console
from rich.table import Table

from little_dorrit_editor.config import get_model, ModelConfig
from little_dorrit_editor.types import EditAnnotation, EditMatch, EditType, EvaluationResult
from little_dorrit_editor.utils import extract_json_from_llm_response


class LLMJudge:
    """Judge that uses an LLM API to evaluate the correctness of predicted edits."""

    def __init__(self, model_id: str = "gpt-4o") -> None:
        """Initialize the LLM judge.

        Args:
            model_id: Model identifier from configuration
        """
        # Get model configuration
        model_config = get_model(model_id)

        # Initialize the OpenAI client with the appropriate base URL and API key
        client_params = {"api_key": model_config.api_key}
        if model_config.endpoint:
            client_params["base_url"] = model_config.endpoint
        self.client = openai.Client(**client_params)
        self.model = model_config.model_name
        self.model_name = model_config.logical_name

        self.console = Console()

    def _create_prompt(
        self, ground_truth_edit: Dict[str, Any], predicted_edit: Dict[str, Any]
    ) -> str:
        """Create a prompt for the LLM to judge an edit.

        Args:
            ground_truth_edit: The ground truth edit operation
            predicted_edit: The predicted edit operation

        Returns:
            A formatted prompt string
        """
        return f"""You are a judge evaluating the accuracy of a multimodal language model in interpreting handwritten editorial corrections in printed text.

GROUND TRUTH EDIT:
```json
{json.dumps(ground_truth_edit, indent=2)}
```

PREDICTED EDIT:
```json
{json.dumps(predicted_edit, indent=2)}
```

Evaluate if the predicted edit correctly captures the intention of the ground truth edit. IGNORE LINE NUMBERS COMPLETELY for this evaluation. Focus only on:

1. Edit Type Accuracy:
   - The edit type must match exactly (e.g., "punctuation", "capitalization", "insertion", etc.)
   - If types differ, the prediction is incorrect

2. Text Content Accuracy:
   - The prediction should capture the CORE change that the ground truth identifies
   - The prediction may include additional context (more words before/after the change)
   - Focus on whether the essential edit (the actual change) is correctly captured
   - For example, if ground truth shows "text" → "text," and prediction shows "some text" → "some text,", this is correct

An edit is considered correct ONLY if both the edit type and the text content accurately match the ground truth's intention.

Respond with a JSON object containing:
{{
  "is_correct": true/false,
  "reasoning": "Detailed explanation of your decision, addressing each criterion"
}}"""

    def evaluate_edit(
        self, ground_truth_edit: Dict[str, Any], predicted_edit: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate a single edit prediction against ground truth.

        Args:
            ground_truth_edit: The ground truth edit
            predicted_edit: The model's predicted edit

        Returns:
            A dict with evaluation results
        """
        prompt = self._create_prompt(ground_truth_edit, predicted_edit)

        self.console.print("[dim]Evaluating edit...[/dim]", end="")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert editor and evaluator."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        self.console.print(" [green]Done[/green]")

        result = extract_json_from_llm_response(response.choices[0].message.content)
        return result


def match_edits(
    ground_truth: EditAnnotation, prediction: EditAnnotation
) -> Tuple[List[Tuple[Dict[str, Any], Dict[str, Any]]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Match predicted edits to ground truth edits.

    Args:
        ground_truth: Ground truth annotation
        prediction: Predicted annotation

    Returns:
        Tuple of (true positives, false positives, false negatives)
    """
    # Convert to dict for easier comparison
    gt_edits = [edit.model_dump() for edit in ground_truth.edits]

    # Filter out any predicted edits without line numbers
    filtered_pred_edits = []
    skipped_count = 0
    for edit in prediction.edits:
        edit_dict = edit.model_dump()
        if edit_dict.get("line_number") is not None:
            filtered_pred_edits.append(edit_dict)
        else:
            skipped_count += 1

    # Log a warning if any edits were skipped
    if skipped_count > 0:
        console = Console()
        console.print(f"[yellow]Warning: Skipped {skipped_count} predicted edit(s) with missing line numbers[/yellow]")

    # This is a simplified matching algorithm
    true_positives = []
    false_positives = list(filtered_pred_edits)
    false_negatives = []

    for gt_edit in gt_edits:
        matched = False
        for i, pred_edit in enumerate(false_positives):
            # Match based on edit type and approximate line number (±3 lines)
            if (
                gt_edit["type"].lower() == pred_edit["type"].lower()
                and abs(gt_edit["line_number"] - pred_edit["line_number"]) <= 3
                # Simple text overlap check
                and (
                    gt_edit["original_text"] in pred_edit["original_text"]
                    or pred_edit["original_text"] in gt_edit["original_text"]
                    or gt_edit["corrected_text"] in pred_edit["corrected_text"]
                    or pred_edit["corrected_text"] in gt_edit["corrected_text"]
                )
            ):
                true_positives.append((gt_edit, pred_edit))
                false_positives.pop(i)
                matched = True
                break

        if not matched:
            false_negatives.append(gt_edit)

    return true_positives, false_positives, false_negatives


def calculate_metrics(
    true_positives: List[Tuple[Dict[str, Any], Dict[str, Any]]],
    false_positives: List[Dict[str, Any]],
    false_negatives: List[Dict[str, Any]],
    judgments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calculate evaluation metrics.

    Args:
        true_positives: List of (ground_truth, prediction) pairs
        false_positives: List of incorrect predictions
        false_negatives: List of missed ground truth edits
        judgments: LLM judgments for each true positive pair

    Returns:
        Dict of evaluation metrics
    """
    # Sum scores from judgments (using penalty-adjusted scores)
    total_score = sum(j["score"] for j in judgments)

    # Count judgments with score >= 0.5 as "correct" for binary metrics
    correct_count = sum(1 for j in judgments if j.get("is_correct_with_penalty", j["is_correct"]))

    # Calculate metrics
    if total_score == 0:
        precision = 0.0
        recall = 0.0
        f1 = 0.0
    else:
        # Using fractional scores for more nuanced evaluation
        precision = total_score / (len(judgments) + len(false_positives))
        recall = total_score / (len(judgments) + len(false_negatives))
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Per-edit-type metrics
    edit_types = set()
    for tp in true_positives:
        edit_types.add(tp[0]["type"].lower())
    for fp in false_positives:
        edit_types.add(fp["type"].lower())
    for fn in false_negatives:
        edit_types.add(fn["type"].lower())

    type_metrics = {}
    for edit_type in edit_types:
        # Get judgments and true positives for this type
        type_judgment_pairs = [
            (j, tp)
            for (tp, _), j in zip(true_positives, judgments)
            if tp["type"].lower() == edit_type
        ]
        type_fps = [fp for fp in false_positives if fp["type"].lower() == edit_type]
        type_fns = [fn for fn in false_negatives if fn["type"].lower() == edit_type]

        # Calculate total score for this type (using penalty-adjusted scores)
        type_total_score = sum(j["score"] for j, _ in type_judgment_pairs)

        # Count for binary metrics (judged correct after penalties)
        type_correct = sum(1 for j, _ in type_judgment_pairs if j.get("is_correct_with_penalty", j["is_correct"]))

        if type_total_score == 0:
            type_precision = 0.0
            type_recall = 0.0
            type_f1 = 0.0
        else:
            # Using fractional scores for more nuanced type-specific evaluation
            type_precision = type_total_score / (len(type_judgment_pairs) + len(type_fps))
            type_recall = type_total_score / (len(type_judgment_pairs) + len(type_fns))
            type_f1 = (
                2 * (type_precision * type_recall) / (type_precision + type_recall)
                if (type_precision + type_recall) > 0
                else 0.0
            )

        type_metrics[edit_type] = {
            "precision": type_precision,
            "recall": type_recall,
            "f1": type_f1,
            "count": len(type_judgment_pairs) + len(type_fns),
        }

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "by_type": type_metrics,
        "correct_count": correct_count,
        "total_ground_truth": len(true_positives) + len(false_negatives),
        "total_predicted": len(true_positives) + len(false_positives),
    }


def evaluate(
    ground_truth_path: Path,
    prediction_path: Path,
    model_name: str = "unnamed_model",
    llm_model: str = "gpt-4.5-preview",
) -> EvaluationResult:
    """Evaluate predictions against ground truth.

    Args:
        ground_truth_path: Path to ground truth JSON file
        prediction_path: Path to prediction JSON file
        model_name: Name of the model being evaluated
        llm_model: Model ID to use for LLM judging

    Returns:
        Evaluation results
    """
    # Helper function to calculate line number penalty
    def get_penalty(gt_line, pred_line):
        """Calculate line number penalty based on distance between lines.
        
        Args:
            gt_line: Ground truth line number
            pred_line: Predicted line number
            
        Returns:
            Float penalty value between 0.0 and 1.0
        """
        line_diff = abs(gt_line - pred_line)
        # Penalty formula: 0.1 * distance^2, capped at 1.0
        return min(1.0, 0.1 * (line_diff ** 2))
    console = Console()

    # Load annotations
    console.print(f"Loading ground truth from [bold]{ground_truth_path}[/bold]")
    with open(ground_truth_path, "r") as f:
        ground_truth = EditAnnotation.model_validate(json.load(f))

    console.print(f"Loading predictions from [bold]{prediction_path}[/bold]")
    with open(prediction_path, "r") as f:
        prediction = EditAnnotation.model_validate(json.load(f))

    # Match edits
    console.print("Matching predicted edits to ground truth...")
    true_positives, false_positives, false_negatives = match_edits(
        ground_truth, prediction
    )

    # Initialize LLM judge
    judge = LLMJudge(model_id=llm_model)

    # Evaluate matching edits
    console.print(f"Found {len(true_positives)} potential matches to evaluate")

    # Prepare the list of EditMatch objects for the result
    edit_matches: List[EditMatch] = []

    # We need to track ground truth edits that have alternate matches
    gt_edits_in_true_positives = {}
    
    # Store judgments to avoid duplicate LLM calls
    judgments = {}
    
    # First, count how many times each ground truth edit appears in true_positives
    for gt_edit, _ in true_positives:
        gt_edit_id = id(gt_edit)
        gt_edits_in_true_positives[gt_edit_id] = gt_edits_in_true_positives.get(gt_edit_id, 0) + 1
    
    # Keep a copy of the original true positives list
    remaining_true_positives = list(true_positives)
    
    # Keep track of indices for the edit_matches
    valid_match_index = 0
    
    # First pass: Process true positives, removing invalid matches
    i = 0
    while i < len(remaining_true_positives):
        gt_edit, pred_edit = remaining_true_positives[i]
        
        # Get line numbers for penalty calculation
        gt_line = gt_edit.get("line_number", 0)
        pred_line = pred_edit.get("line_number", 1000)  # Use a large default to ensure penalty if missing
        
        # Create a key to uniquely identify this gt_edit/pred_edit pair
        pair_key = (id(gt_edit), id(pred_edit))
        
        # Get the basic correctness judgment (ignoring line numbers)
        # Only make the LLM call once and store the result
        if pair_key not in judgments:
            judgments[pair_key] = judge.evaluate_edit(gt_edit, pred_edit)
        
        judgment = judgments[pair_key]
        
        # Calculate line number penalty
        line_penalty = get_penalty(gt_line, pred_line)
        
        # Store line diff and penalty in the judgment for reuse
        line_diff = abs(gt_line - pred_line)
        judgment["line_diff"] = line_diff
        judgment["line_penalty"] = line_penalty
        
        # Combined condition: content must match AND line penalty must not be complete (1.0)
        is_correct = judgment.get("is_correct", False) and not line_penalty >= 1.0
        
        if not is_correct:
            # Move pred_edit to false_positives list
            false_positives.append(pred_edit)
            
            # Decrement the count for this ground truth edit
            gt_edit_id = id(gt_edit)
            gt_edits_in_true_positives[gt_edit_id] -= 1
            
            # If this ground truth edit has no other matches, add it to false_negatives
            if gt_edits_in_true_positives[gt_edit_id] == 0:
                false_negatives.append(gt_edit)
            
            # Remove this pair from the remaining_true_positives and continue to next item
            remaining_true_positives.pop(i)
            continue
        
        # Move to next item
        i += 1
    
    # Second pass: Process the valid matches
    for i, (gt_edit, pred_edit) in enumerate(remaining_true_positives):
        # Get line number for display
        pred_line = pred_edit.get("line_number", 0)
        
        # Retrieve the judgment and pre-calculated penalty info
        pair_key = (id(gt_edit), id(pred_edit))
        judgment = judgments[pair_key]
        reasoning = judgment.get("reasoning", "")
        
        # Get the line diff and penalty we stored in the first pass
        line_diff = judgment.get("line_diff", 0)
        line_penalty = judgment.get("line_penalty", 0.0)
        
        # Calculate score after penalty
        score = max(0.0, 1.0 - line_penalty)
        # A judgment is "correct" if score >= 0.5 after applying penalty
        is_correct_with_penalty = score >= 0.5
        
        # Create an EditMatch for this matched pair with appropriate tp/fp/fn values
        # For matched pairs, tp = score, fp = (1 - score)/2, fn = (1 - score)/2 to maintain tp+fp+fn=1
        edit_match = EditMatch(
            observed_edit_num=valid_match_index,                # Index in valid predictions
            expected_edit_num=valid_match_index,                # Index in matched ground truth
            tp=score,                                           # True positive score
            fp=(1.0 - score) / 2,                               # False positive portion
            fn=(1.0 - score) / 2,                               # False negative portion
            type=EditType(pred_edit.get("type", "unknown")),    # Edit type from prediction
            original_text=pred_edit.get("original_text", ""),   # Text from prediction
            corrected_text=pred_edit.get("corrected_text", ""), # Text from prediction
            observed_line_number=pred_line,                     # Line number from prediction
            line_diff=line_diff,                                # Difference in line numbers
            line_number_penalty=line_penalty,                   # Penalty applied
            judgement=reasoning                                 # Reasoning from judge
        )
        edit_matches.append(edit_match)
        valid_match_index += 1
        
    # We've now updated true_positives, false_positives, and false_negatives
    # Replace the original true_positives list
    true_positives = remaining_true_positives

    # Process false positives (predicted edits that don't match any ground truth)
    for i, fp_edit in enumerate(false_positives):
        # These are pure false positives (fp=1, tp=fn=0)
        edit_match = EditMatch(
            observed_edit_num=valid_match_index + i,            # Index in predictions after valid matches
            expected_edit_num=None,                             # No matching ground truth
            tp=0.0,                                             # No true positive component
            fp=1.0,                                             # Pure false positive
            fn=0.0,                                             # No false negative component
            type=EditType(fp_edit.get("type", "unknown")),      # Edit type from prediction
            original_text=fp_edit.get("original_text", ""),     # Text from prediction
            corrected_text=fp_edit.get("corrected_text", ""),   # Text from prediction
            observed_line_number=fp_edit.get("line_number"),    # Line number from prediction
            line_diff=None,                                     # No line difference (no match)
            line_number_penalty=0.0,                            # No penalty (no match)
            judgement="False positive: no matching ground truth edit found"
        )
        edit_matches.append(edit_match)

    # Process false negatives (ground truth edits that weren't found in the prediction)
    for i, fn_edit in enumerate(false_negatives):
        # These are pure false negatives (fn=1, tp=fp=0)
        edit_match = EditMatch(
            observed_edit_num=None,                             # No matching prediction
            expected_edit_num=valid_match_index + i,            # Index in ground truth after valid matches
            tp=0.0,                                             # No true positive component
            fp=0.0,                                             # No false positive component
            fn=1.0,                                             # Pure false negative
            type=EditType(fn_edit.get("type", "unknown")),      # Edit type from ground truth
            original_text=fn_edit.get("original_text", ""),     # Text from ground truth
            corrected_text=fn_edit.get("corrected_text", ""),   # Text from ground truth
            observed_line_number=None,                          # No line number (no match)
            line_diff=None,                                     # No line difference (no match)
            line_number_penalty=0.0,                            # No penalty (no match)
            judgement="False negative: ground truth edit not found in prediction"
        )
        edit_matches.append(edit_match)

    # Create evaluation result in the new format
    result = EvaluationResult(
        model_name=model_name,
        date=datetime.now().isoformat(),
        annotator=prediction.annotator or model_name,  # Use the annotator from prediction if available
        annotation_date=prediction.annotation_date,    # Use the annotation date from prediction
        details=edit_matches
    )

    return result


def display_results(result: EvaluationResult) -> None:
    """Display evaluation results in a nice table.

    Args:
        result: Evaluation results
    """
    console = Console()

    # Calculate summary metrics from detailed results
    total_tp = sum(edit.tp for edit in result.details)
    total_fp = sum(edit.fp for edit in result.details)
    total_fn = sum(edit.fn for edit in result.details)

    # Calculate precision, recall, F1
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Count "correct" edits (tp >= 0.5)
    correct_count = sum(1 for edit in result.details if edit.tp >= 0.5)
    expected_count = sum(1 for edit in result.details if edit.expected_edit_num is not None)

    # Main metrics table
    table = Table(title=f"Evaluation Results for {result.model_name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Precision", f"{precision:.4f}")
    table.add_row("Recall", f"{recall:.4f}")
    table.add_row("F1 Score", f"{f1_score:.4f}")
    table.add_row("Correct / Total", f"{correct_count} / {expected_count}")

    console.print(table)

    # Calculate metrics by edit type
    metrics_by_type = {}
    for edit in result.details:
        if edit.type:
            edit_type = str(edit.type)
            if edit_type not in metrics_by_type:
                metrics_by_type[edit_type] = {
                    "tp": 0.0, "fp": 0.0, "fn": 0.0, "count": 0
                }

            metrics_by_type[edit_type]["tp"] += edit.tp
            metrics_by_type[edit_type]["fp"] += edit.fp
            metrics_by_type[edit_type]["fn"] += edit.fn

            # Count as part of this type if it's a match or false negative
            if edit.expected_edit_num is not None:
                metrics_by_type[edit_type]["count"] += 1

    # Per-type metrics table
    type_table = Table(title="Results by Edit Type")
    type_table.add_column("Edit Type", style="cyan")
    type_table.add_column("Precision", style="green")
    type_table.add_column("Recall", style="green")
    type_table.add_column("F1 Score", style="green")
    type_table.add_column("Count", style="dim")

    for edit_type, metrics in metrics_by_type.items():
        type_precision = metrics["tp"] / (metrics["tp"] + metrics["fp"]) if (metrics["tp"] + metrics["fp"]) > 0 else 0.0
        type_recall = metrics["tp"] / (metrics["tp"] + metrics["fn"]) if (metrics["tp"] + metrics["fn"]) > 0 else 0.0
        type_f1 = 2 * type_precision * type_recall / (type_precision + type_recall) if (type_precision + type_recall) > 0 else 0.0

        type_table.add_row(
            edit_type,
            f"{type_precision:.4f}",
            f"{type_recall:.4f}",
            f"{type_f1:.4f}",
            str(metrics["count"]),
        )

    console.print(type_table)

    # Show details about line number penalties
    edits_with_penalties = [edit for edit in result.details if edit.line_number_penalty > 0]
    if edits_with_penalties:
        console.print("\n[bold cyan]Line Number Penalties:[/bold cyan]")
        console.print("Edits with line number differences incur penalties based on the formula: 0.1 * distance^2")
        console.print("- 1 line off: -0.1 points")
        console.print("- 2 lines off: -0.4 points")
        console.print("- 3 lines off: -0.9 points")
        console.print("- >3 lines off: -1.0 (full penalty)")

        # Get penalties and diffs
        penalties = [edit.line_number_penalty for edit in result.details if edit.line_number_penalty is not None]
        line_diffs = [edit.line_diff for edit in result.details if edit.line_diff is not None]
        non_zero_diffs = [diff for diff in line_diffs if diff > 0]

        # Calculate stats
        if penalties:
            total_penalty = sum(penalties)
            avg_penalty = total_penalty / len(penalties) if penalties else 0.0

            console.print("\n[bold cyan]Line Difference Statistics:[/bold cyan]")
            console.print(f"Total evaluated edits: {len(penalties)}")
            console.print(f"Edits with line differences: {len(non_zero_diffs)}")
            if non_zero_diffs:
                console.print(f"Average line difference: {sum(non_zero_diffs) / len(non_zero_diffs):.2f}")
            console.print(f"Total line number penalty: {total_penalty:.2f}")
            console.print(f"Average penalty per edit: {avg_penalty:.2f}")

            # Show penalties by match
            console.print("\n[bold cyan]Penalties by Match:[/bold cyan]")
            for i, edit in enumerate(edits_with_penalties):
                if edit.line_number_penalty > 0:
                    content_match = edit.tp > 0
                    final_match = edit.tp >= 0.5
                    console.print(f"{i+1}. Line diff: {edit.line_diff}, Penalty: {edit.line_number_penalty:.2f}, " +
                                  f"Content match: {'✓' if content_match else '✗'}, " +
                                  f"Final match: {'✓' if final_match else '✗'}")