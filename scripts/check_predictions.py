#!/usr/bin/env python
"""
Prediction Directory Analysis Tool

This script analyzes the predictions directory structure and reports on:
1. Questions/files present for each model
2. Number of runs per question
3. Missing evaluations for prediction files
4. Inconsistencies in run counts across questions

It highlights any anomalies or uneven distributions in the data and can suggest
commands to fix these issues.

Features:
---------
- Detects missing questions or uneven run counts across questions
- Identifies missing evaluations for existing prediction files
- Suggests commands to balance the dataset
- Supports two checking modes: standard and strict

Checking Modes:
--------------
1. Standard Mode (default): Checks for internal consistency only
   - A model is considered "OK" if all its questions have the same number of runs
   - The specific number of runs doesn't matter (could be 1, 2, or more)
   - Suggested fixes aim to make all questions have the same number of runs
     (using the most common run count in that model as the target)

2. Strict Mode (--strict): Requires exactly the target number of runs
   - A model is only considered "OK" if all questions have the target number of runs
   - The target is specified with --target-runs (default: 3)
   - Suggested fixes aim to make all questions have exactly the target number of runs

Command-line Options:
--------------------
--predict-dir PATH    Path to predictions directory (default: ./predictions)
--target-runs N       Target number of runs per question (default: 3)
--suggest-fixes       Suggest commands to fix dataset balance (default: True)
--no-suggest-fixes    Don't suggest commands to fix dataset balance
--strict              Use strict checking that requires the exact target number of runs

Example Usage:
-------------
# Standard analysis (internal consistency only)
python scripts/check_predictions.py

# Strict analysis requiring exactly 3 runs per question
python scripts/check_predictions.py --strict

# Specify a different target number of runs
python scripts/check_predictions.py --strict --target-runs 2

# Don't suggest fixes
python scripts/check_predictions.py --no-suggest-fixes

The suggested fix commands will use the new --question-ids parameter in
run_prediction.sh and run_evaluation.sh to only process the specific questions
that need more runs or evaluations.
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
import json
from rich.console import Console
from rich.table import Table
from rich import box


@dataclass
class ModelStats:
    """Statistics for a single model."""
    model_id: str
    display_name: str
    question_runs: Dict[str, List[str]]  # question_id -> list of run_ids
    missing_evaluations: List[Tuple[str, str]]  # (question_id, run_id) pairs


def extract_file_info(filename: str) -> Tuple[str, str, str]:
    """Extract question ID, run ID, and date from filename."""
    pattern = r"^(\d+)_(\d+)_(\d+)_prediction\.json$"
    match = re.match(pattern, filename)
    if match:
        question_id, run_id, date = match.groups()
        return question_id, run_id, date
    return None, None, None


def get_model_display_name(model_dir: Path) -> str:
    """Get the display name from the model's config.json file."""
    config_path = model_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("display_name", model_dir.name)
        except (json.JSONDecodeError, IOError):
            pass
    return model_dir.name


def analyze_predictions(predictions_dir: Path) -> List[ModelStats]:
    """Analyze the predictions directory and gather statistics."""
    model_stats = []
    
    # Find all model directories
    model_dirs = [d for d in predictions_dir.iterdir() if d.is_dir()]
    
    for model_dir in model_dirs:
        model_id = model_dir.name
        display_name = get_model_display_name(model_dir)
        
        # Check if prediction and results directories exist
        pred_dir = model_dir / "predictions" / "eval"
        results_dir = model_dir / "results" / "eval"
        
        if not pred_dir.exists() or not pred_dir.is_dir():
            # Skip if no predictions directory
            continue
        
        # Initialize stats
        question_runs = defaultdict(list)
        missing_evaluations = []
        
        # Process prediction files
        for pred_file in pred_dir.glob("*_prediction.json"):
            filename = pred_file.name
            question_id, run_id, date = extract_file_info(filename)
            
            if question_id is None:
                continue
                
            # Map question ID to run ID
            question_runs[question_id].append(run_id)
            
            # Check if corresponding evaluation exists
            results_file = results_dir / filename.replace("_prediction.json", "_results.json")
            if not results_file.exists():
                missing_evaluations.append((question_id, run_id))
        
        # Sort run IDs for consistent display
        for question_id in question_runs:
            question_runs[question_id].sort()
            
        # Create stats object
        stats = ModelStats(
            model_id=model_id,
            display_name=display_name,
            question_runs=dict(question_runs),
            missing_evaluations=missing_evaluations
        )
        model_stats.append(stats)
    
    return model_stats


def find_anomalies(stats: ModelStats, target_runs: int = None) -> Tuple[bool, Set[str], Dict[str, int]]:
    """Find anomalies in the question runs data.
    
    Args:
        stats: Model statistics
        target_runs: Optional target number of runs to check against
        
    Returns:
        Tuple of (has_anomalies, missing_questions, run_counts)
    """
    has_anomalies = False
    
    # Check for missing questions (assuming consecutive question IDs)
    if not stats.question_runs:
        return True, set(), {}
        
    all_questions = set(stats.question_runs.keys())
    min_q = min(int(q) for q in all_questions)
    max_q = max(int(q) for q in all_questions)
    expected_questions = set(f"{i:03d}" for i in range(min_q, max_q + 1))
    missing_questions = expected_questions - all_questions
    if missing_questions:
        has_anomalies = True
    
    # Check for uneven run counts
    run_counts = {q: len(runs) for q, runs in stats.question_runs.items()}
    count_values = set(run_counts.values())
    
    # First check internal consistency (all questions have same count)
    if len(count_values) > 1:
        has_anomalies = True
    
    # If target_runs is provided, also check if any questions have fewer runs than target
    if target_runs is not None:
        for count in count_values:
            if count < target_runs:
                has_anomalies = True
                break
        
    return has_anomalies, missing_questions, run_counts


def print_report(model_stats: List[ModelStats], console: Console, target_runs: int = None) -> None:
    """Print a formatted report of the analysis.
    
    Args:
        model_stats: List of model statistics
        console: Rich console for output
        target_runs: Optional target number of runs to check against
    """
    if not model_stats:
        console.print("[yellow]No prediction data found![/yellow]")
        return
    
    # Sort models by ID
    model_stats.sort(key=lambda x: x.model_id)
    
    # Create summary table
    summary_table = Table(title="Model Prediction Summary", box=box.ROUNDED)
    summary_table.add_column("Model ID", style="cyan")
    summary_table.add_column("Display Name", style="green")
    summary_table.add_column("Questions", justify="right")
    summary_table.add_column("Status", style="bold")
    
    # Create detailed table for each model with issues
    detailed_tables = []
    
    for stats in model_stats:
        has_anomalies, missing_questions, run_counts = find_anomalies(stats, target_runs)
        
        # Determine status
        status = "[green]OK[/green]"
        if not stats.question_runs:
            status = "[red]NO DATA[/red]"
        elif has_anomalies or stats.missing_evaluations:
            status = "[red]ISSUES[/red]"
        
        # Add to summary table
        question_count = len(stats.question_runs) if stats.question_runs else 0
        summary_table.add_row(
            stats.model_id,
            stats.display_name,
            str(question_count),
            status
        )
        
        # If there are issues, create a detailed table
        if has_anomalies or stats.missing_evaluations:
            detail_table = Table(
                title=f"Details for {stats.display_name} ({stats.model_id})",
                box=box.SIMPLE
            )
            detail_table.add_column("Question ID", style="cyan")
            detail_table.add_column("Runs", style="green")
            detail_table.add_column("Missing Evals", style="yellow")
            detail_table.add_column("Notes", style="red")
            
            # Get all question IDs (including missing ones)
            all_qs = set(stats.question_runs.keys()) | missing_questions
            for q in sorted(all_qs, key=int):
                runs = stats.question_runs.get(q, [])
                run_str = ", ".join(runs) if runs else "NONE"
                
                # Find missing evaluations for this question
                missing_evals = [r for (qid, r) in stats.missing_evaluations if qid == q]
                missing_str = ", ".join(missing_evals) if missing_evals else "None"
                
                notes = []
                if q in missing_questions:
                    notes.append("Missing question")
                
                # Check if this question has fewer/more runs than others
                if runs and run_counts and len(run_counts) > 1:
                    most_common_count = max(set(run_counts.values()), key=list(run_counts.values()).count)
                    if len(runs) != most_common_count:
                        if len(runs) < most_common_count:
                            notes.append(f"Fewer runs than expected ({len(runs)} vs {most_common_count})")
                        else:
                            notes.append(f"More runs than expected ({len(runs)} vs {most_common_count})")
                
                notes_str = ", ".join(notes)
                
                # Color the row based on status
                if q in missing_questions:
                    style = "red"
                elif missing_evals:
                    style = "yellow"
                elif notes:
                    style = "yellow"
                else:
                    style = None
                    
                detail_table.add_row(q, run_str, missing_str, notes_str, style=style)
            
            detailed_tables.append(detail_table)
    
    # Print the tables
    console.print(summary_table)
    console.print()
    
    if detailed_tables:
        console.print("[bold red]The following models have issues:[/bold red]")
        for table in detailed_tables:
            console.print()
            console.print(table)
    else:
        console.print("[bold green]All models have consistent data and evaluations![/bold green]")


def find_model_unbalanced_questions(stats: ModelStats, target_runs: int = 3, strict: bool = False) -> Dict[str, int]:
    """Find questions that need more runs to reach the target number.
    
    Args:
        stats: Model statistics
        target_runs: Target number of runs per question
        strict: Whether to use strict checking that requires the exact target number
        
    Returns:
        Dict mapping question IDs to number of additional runs needed
    """
    needs_more_runs = {}
    
    # Skip models without data
    if not stats.question_runs:
        return needs_more_runs
    
    # Find the most common run count across all questions
    run_counts = {q: len(runs) for q, runs in stats.question_runs.items()}
    count_values = list(run_counts.values())
    
    # If empty, nothing to do
    if not count_values:
        return needs_more_runs
    
    # Determine target count
    if strict:
        # In strict mode, use the specified target
        target_count = target_runs
    else:
        # In non-strict mode, use the most common count within this model
        most_common_count = max(set(count_values), key=count_values.count)
        target_count = most_common_count
    
    # Check each question
    for question_id, runs in stats.question_runs.items():
        current_runs = len(runs)
        if current_runs < target_count:
            needs_more_runs[question_id] = target_count - current_runs
    
    return needs_more_runs


def generate_prediction_commands(model_stats: List[ModelStats], target_runs: int = 3, strict: bool = False) -> Dict[str, List[str]]:
    """Generate commands to balance prediction runs.
    
    Args:
        model_stats: List of model statistics
        target_runs: Target number of runs per question
        strict: Whether to use strict checking that requires the exact target number
        
    Returns:
        Dict mapping model IDs to lists of commands to run
    """
    commands = defaultdict(list)
    
    for stats in model_stats:
        # Find questions needing more runs
        needed_runs = find_model_unbalanced_questions(stats, target_runs, strict)
        
        if needed_runs:
            # Generate question_ids parameter
            question_ids = ",".join(needed_runs.keys())
            
            # Create command
            command = f"./scripts/run_prediction.sh {stats.model_id} --question-ids \"{question_ids}\""
            commands[stats.model_id].append(command)
            
    return dict(commands)


def generate_evaluation_commands(model_stats: List[ModelStats]) -> Dict[str, List[str]]:
    """Generate commands to run missing evaluations.
    
    Args:
        model_stats: List of model statistics
        
    Returns:
        Dict mapping model IDs to lists of commands to run
    """
    commands = defaultdict(list)
    
    for stats in model_stats:
        # If there are missing evaluations, run evaluation for this model
        if stats.missing_evaluations:
            # Group missing evaluations by question ID
            missing_by_question = defaultdict(list)
            for question_id, run_id in stats.missing_evaluations:
                missing_by_question[question_id].append(run_id)
            
            # Generate question_ids parameter
            question_ids = ",".join(missing_by_question.keys())
            
            # Create command
            command = f"./scripts/run_evaluation.sh {stats.model_id} --question-ids \"{question_ids}\" --force"
            commands[stats.model_id].append(command)
            
    return dict(commands)


def print_fix_suggestions(model_stats: List[ModelStats], console: Console, target_runs: int = 3, strict: bool = False):
    """Print suggestions to fix dataset balance.
    
    Args:
        model_stats: List of model statistics
        console: Rich console for output
        target_runs: Target number of runs per question
        strict: Whether to use strict checking that requires the exact target number
    """
    # Generate commands
    prediction_commands = generate_prediction_commands(model_stats, target_runs, strict)
    evaluation_commands = generate_evaluation_commands(model_stats)
    
    console.print()
    console.print("[bold cyan]Suggested commands to fix dataset balance:[/bold cyan]")
    console.print()
    
    # Add prediction commands
    if prediction_commands:
        console.print("[bold green]Commands to add missing prediction runs:[/bold green]")
        for model_id, commands in prediction_commands.items():
            console.print(f"[yellow]Model: {model_id}[/yellow]")
            for cmd in commands:
                console.print(f"{cmd}")
            console.print()
    else:
        console.print("[green]No missing prediction runs found[/green]")
        console.print()
    
    # Add evaluation commands
    if evaluation_commands:
        console.print("[bold green]Commands to run missing evaluations:[/bold green]")
        for model_id, commands in evaluation_commands.items():
            console.print(f"[yellow]Model: {model_id}[/yellow]")
            for cmd in commands:
                console.print(f"{cmd}")
            console.print()
    else:
        console.print("[green]No missing evaluations found[/green]")
        console.print()


def main():
    """Main function."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Check prediction directory balance")
    parser.add_argument(
        "--predict-dir",
        type=Path,
        default=None,
        help="Path to predictions directory (default: ./predictions)"
    )
    parser.add_argument(
        "--target-runs",
        type=int,
        default=3,
        help="Target number of runs per question (default: 3)"
    )
    parser.add_argument(
        "--suggest-fixes",
        action="store_true",
        default=True,
        help="Suggest commands to fix dataset balance (default: True)"
    )
    parser.add_argument(
        "--no-suggest-fixes",
        action="store_false",
        dest="suggest_fixes",
        help="Don't suggest commands to fix dataset balance"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Use strict checking that requires the exact target number of runs (default: False)"
    )
    
    args = parser.parse_args()
    
    # Get predictions directory
    project_root = Path(__file__).parent.parent
    predictions_dir = args.predict_dir or (project_root / "predictions")
    
    if not predictions_dir.exists():
        print(f"Error: Predictions directory not found at {predictions_dir}")
        sys.exit(1)
    
    # Initialize rich console
    console = Console()
    
    # Analyze predictions
    console.print(f"[bold]Analyzing predictions in {predictions_dir}...[/bold]")
    model_stats = analyze_predictions(predictions_dir)
    
    # Print report
    console.print()
    if args.strict:
        console.print(f"[yellow]Using strict checking mode (target: {args.target_runs} runs per question)[/yellow]")
        print_report(model_stats, console, args.target_runs)
    else:
        console.print("[green]Using standard checking mode (internal consistency only)[/green]")
        print_report(model_stats, console)
    
    # Print fix suggestions if requested
    if args.suggest_fixes:
        print_fix_suggestions(model_stats, console, args.target_runs, args.strict)


if __name__ == "__main__":
    main()