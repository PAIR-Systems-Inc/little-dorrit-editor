"""Evaluation logic for the Little Dorrit Editor benchmark."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openai
from rich.console import Console
from rich.table import Table

from little_dorrit_editor.config import get_model, ModelConfig
from little_dorrit_editor.types import EditAnnotation, EvaluationResult


class LLMJudge:
    """Judge that uses an LLM API to evaluate the correctness of predicted edits."""

    def __init__(
        self, model_id: str = "gpt-4o", api_key: Optional[str] = None
    ) -> None:
        """Initialize the LLM judge.

        Args:
            model_id: Model identifier from configuration
            api_key: API key (optional, overrides configuration)
        """
        # Get model configuration
        model_config = get_model(model_id)
        
        # Allow API key override
        if api_key is None:
            api_key = model_config.api_key
            
        # Initialize the OpenAI client with the appropriate base URL and API key
        self.client = openai.Client(
            api_key=api_key,
            base_url=model_config.endpoint
        )
        self.model = model_config.model_name
            
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
        
        result = json.loads(response.choices[0].message.content)
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
    api_key: Optional[str] = None,
    llm_model: str = "gpt-4o",
) -> EvaluationResult:
    """Evaluate predictions against ground truth.

    Args:
        ground_truth_path: Path to ground truth JSON file
        prediction_path: Path to prediction JSON file
        model_name: Name of the model being evaluated
        api_key: API key (optional, overrides configuration)
        llm_model: Model ID to use for LLM judging

    Returns:
        Evaluation results
    """
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
    judge = LLMJudge(model_id=llm_model, api_key=api_key)
    
    # Evaluate matching edits
    console.print(f"Found {len(true_positives)} potential matches to evaluate")
    judgments = []
    
    for gt_edit, pred_edit in true_positives:
        # Get the basic correctness judgment (ignoring line numbers)
        judgment = judge.evaluate_edit(gt_edit, pred_edit)
        
        # Calculate line number penalty: 0.1 * distance^2
        # Default to a large difference if line numbers are missing (shouldn't happen with filtering)
        gt_line = gt_edit.get("line_number", 0)
        pred_line = pred_edit.get("line_number", 1000)  # Use a large default to ensure penalty if missing
        line_diff = abs(gt_line - pred_line)
        line_penalty = min(1.0, 0.1 * (line_diff ** 2))  # Cap at 1.0
        
        # Apply penalty only if the edit is otherwise correct
        if judgment["is_correct"]:
            # Calculate score after penalty
            score = max(0.0, 1.0 - line_penalty)
            # A judgment is "correct" if score >= 0.5 after applying penalty
            judgment["is_correct_with_penalty"] = score >= 0.5
        else:
            # If content doesn't match, keep score at 0
            score = 0.0
            judgment["is_correct_with_penalty"] = False
            
        # Add score and penalty information
        judgment["score"] = score
        judgment["line_number_penalty"] = line_penalty
        judgment["line_diff"] = line_diff
            
        judgments.append(judgment)
    
    # Calculate metrics
    console.print("Calculating evaluation metrics...")
    metrics = calculate_metrics(
        true_positives, false_positives, false_negatives, judgments
    )
    
    # Add useful reference data to metrics for detailed analysis
    metrics["judgments"] = judgments
    metrics["true_positives"] = [(gt, pred) for gt, pred in true_positives]
    
    # Create evaluation result
    from datetime import datetime
    
    result = EvaluationResult(
        model_name=model_name,
        precision=metrics["precision"],
        recall=metrics["recall"],
        f1_score=metrics["f1_score"],
        date=datetime.now().isoformat(),
        details=metrics,
    )
    
    return result


def display_results(result: EvaluationResult) -> None:
    """Display evaluation results in a nice table.

    Args:
        result: Evaluation results
    """
    console = Console()
    
    # Main metrics table
    table = Table(title=f"Evaluation Results for {result.model_name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Precision", f"{result.precision:.4f}")
    table.add_row("Recall", f"{result.recall:.4f}")
    table.add_row("F1 Score", f"{result.f1_score:.4f}")
    table.add_row(
        "Correct / Total",
        f"{result.details['correct_count']} / {result.details['total_ground_truth']}",
    )
    
    console.print(table)
    
    # Per-type metrics table
    type_table = Table(title="Results by Edit Type")
    type_table.add_column("Edit Type", style="cyan")
    type_table.add_column("Precision", style="green")
    type_table.add_column("Recall", style="green")
    type_table.add_column("F1 Score", style="green")
    type_table.add_column("Count", style="dim")
    
    for edit_type, metrics in result.details["by_type"].items():
        type_table.add_row(
            edit_type,
            f"{metrics['precision']:.4f}",
            f"{metrics['recall']:.4f}",
            f"{metrics['f1']:.4f}",
            str(metrics['count']),
        )
    
    console.print(type_table)
    
    # Show details about line number penalties
    if "judgments" in result.details and result.details["judgments"]:
        console.print("\n[bold cyan]Line Number Penalties:[/bold cyan]")
        console.print("Edits with line number differences incur penalties based on the formula: 0.1 * distance^2")
        console.print("- 1 line off: -0.1 points")
        console.print("- 2 lines off: -0.4 points")
        console.print("- 3 lines off: -0.9 points")
        console.print("- >3 lines off: -1.0 (full penalty)")
        
        # Get penalties and diffs
        penalties = [j.get("line_number_penalty", 0.0) for j in result.details["judgments"]]
        line_diffs = [j.get("line_diff", 0) for j in result.details["judgments"]]
        non_zero_diffs = [diff for diff in line_diffs if diff > 0]
        
        # Calculate stats
        if penalties:
            total_penalty = sum(penalties)
            avg_penalty = total_penalty / len(penalties)
            
            console.print("\n[bold cyan]Line Difference Statistics:[/bold cyan]")
            console.print(f"Total evaluated edits: {len(penalties)}")
            console.print(f"Edits with line differences: {len(non_zero_diffs)}")
            if non_zero_diffs:
                console.print(f"Average line difference: {sum(non_zero_diffs) / len(non_zero_diffs):.2f}")
            console.print(f"Total line number penalty: {total_penalty:.2f}")
            console.print(f"Average penalty per edit: {avg_penalty:.2f}")
            
            # Show penalties by match
            console.print("\n[bold cyan]Penalties by Match:[/bold cyan]")
            for i, j in enumerate(result.details["judgments"]):
                if j["line_number_penalty"] > 0:
                    content_match = j["is_correct"]
                    final_match = j.get("is_correct_with_penalty", j["is_correct"])
                    console.print(f"{i+1}. Line diff: {j['line_diff']}, Penalty: {j['line_number_penalty']:.2f}, " +
                                  f"Content match: {'✓' if content_match else '✗'}, " +
                                  f"Final match: {'✓' if final_match else '✗'}")