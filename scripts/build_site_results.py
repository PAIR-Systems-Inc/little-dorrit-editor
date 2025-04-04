#!/usr/bin/env python
"""
Build results.json for the website based on predictions directory structure.

This script collects individual result files from prediction directories
and builds a comprehensive JSON structure with per-file results for display
on the leaderboard site.
"""

import json
import datetime
from pathlib import Path
import glob
import re
from typing import Dict, List, Any, Optional


def extract_file_id(filename: str) -> str:
    """Extract the file ID (e.g., '003') from a results filename.
    
    Args:
        filename: Results filename (e.g., '003_01_20250404_results.json')
    
    Returns:
        The file ID (e.g., '003')
    """
    match = re.match(r"(\d+)_\d+_\d+_results\.json", Path(filename).name)
    if match:
        return match.group(1)
    return Path(filename).stem.split("_")[0]


def load_results_file(filepath: Path) -> Dict[str, Any]:
    """Load a single results file.
    
    Args:
        filepath: Path to the results file
    
    Returns:
        JSON data from the file
    """
    with open(filepath, "r") as f:
        return json.load(f)


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load a model's config file.
    
    Args:
        config_path: Path to the config file
    
    Returns:
        Config data or default config if file doesn't exist
    """
    default_config = {
        "model_name": "unknown",
        "shots": 2,
        "temperature": 0.0,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "notes": "Default configuration"
    }
    
    if not config_path.exists():
        print(f"Warning: Config file not found: {config_path}. Using default.")
        return default_config
    
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return default_config


def collect_model_results(predictions_dir: Path, shot_filter: Optional[int] = None) -> List[Dict[str, Any]]:
    """Collect results for all models in the predictions directory.
    
    Args:
        predictions_dir: Path to the predictions directory
        shot_filter: If provided, only include models with this shot count
    
    Returns:
        List of model results with per-file details
    """
    all_model_results = []
    
    # Find all model directories
    model_dirs = [d for d in predictions_dir.iterdir() if d.is_dir()]
    
    for model_dir in model_dirs:
        model_name = model_dir.name
        
        # Load model configuration
        config_path = model_dir / "config.json"
        config = load_config_file(config_path)
        
        # Filter by shot count if requested
        if shot_filter is not None and config.get("shots", 0) != shot_filter:
            print(f"Skipping {model_name} with {config.get('shots')} shots (filter: {shot_filter})")
            continue
        
        # Find all result files - use new directory structure
        results_dir = model_dir / "results" / "eval"
        
        if not results_dir.exists() or not results_dir.is_dir():
            print(f"Warning: No results directory found for model {model_name} at {results_dir}")
            continue
        
        # Find all result files
        result_files = list(results_dir.glob("*_results.json"))
        if not result_files:
            print(f"Warning: No result files found for model {model_name}")
            continue
        
        # Sort result files by file ID
        result_files.sort(key=lambda x: extract_file_id(x.name))
        
        # Load all result files
        file_results = []
        latest_date = None
        
        for result_file in result_files:
            try:
                result_data = load_results_file(result_file)
                
                # Extract the file ID for reference
                file_id = extract_file_id(result_file.name)
                result_data["file_id"] = file_id
                
                # Keep track of the latest result date
                if "date" in result_data:
                    date_str = result_data["date"]
                    try:
                        date = datetime.datetime.fromisoformat(date_str)
                        if latest_date is None or date > latest_date:
                            latest_date = date
                    except (ValueError, TypeError):
                        pass
                
                file_results.append(result_data)
            except Exception as e:
                print(f"Error loading result file {result_file}: {e}")
        
        if not file_results:
            print(f"Warning: No valid result files found for model {model_name}")
            continue
        
        # Format model name for display (capitalize words, preserve known acronyms)
        display_name = model_name
        if re.match(r"^[a-z0-9-]+$", model_name):  # Only transform lowercase names
            # Special case for GPT models
            if model_name.startswith("gpt"):
                parts = model_name.split("-")
                if len(parts) > 1:
                    display_name = parts[0].upper() + "-" + "".join(parts[1:])
            else:
                # Capitalize first letter of each word
                display_name = " ".join(word.capitalize() for word in model_name.replace("-", " ").split())
        
        # Calculate aggregate metrics
        total_gt = sum(fr.get("details", {}).get("total_ground_truth", 0) for fr in file_results)
        total_pred = sum(fr.get("details", {}).get("total_predicted", 0) for fr in file_results)
        total_correct = sum(fr.get("details", {}).get("correct_count", 0) for fr in file_results)
        
        # Calculate precision, recall, F1
        precision = total_correct / total_pred if total_pred > 0 else 0
        recall = total_correct / total_gt if total_gt > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Collect edit types from all files
        edit_types = {}
        for fr in file_results:
            by_type = fr.get("details", {}).get("by_type", {})
            for edit_type, metrics in by_type.items():
                if edit_type not in edit_types:
                    edit_types[edit_type] = {
                        "precision": 0,
                        "recall": 0,
                        "f1": 0,
                        "count": 0
                    }
                
                # Update counts
                edit_types[edit_type]["count"] += metrics.get("count", 0)
                
                # Weight metrics by count
                count = metrics.get("count", 0)
                if count > 0:
                    edit_types[edit_type]["precision"] += metrics.get("precision", 0) * count
                    edit_types[edit_type]["recall"] += metrics.get("recall", 0) * count
                    edit_types[edit_type]["f1"] += metrics.get("f1", 0) * count
        
        # Calculate averages for each edit type
        for edit_type, metrics in edit_types.items():
            if metrics["count"] > 0:
                metrics["precision"] /= metrics["count"]
                metrics["recall"] /= metrics["count"]
                metrics["f1"] /= metrics["count"]
        
        # Create the model result entry
        model_result = {
            "model_name": display_name,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "date": latest_date.isoformat() if latest_date else datetime.datetime.now().isoformat(),
            "shots": config.get("shots", 2),  # Include shot count in the model result
            "config": config,  # Include full configuration
            "details": {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "by_type": edit_types,
                "correct_count": total_correct,
                "total_ground_truth": total_gt,
                "total_predicted": total_pred,
                "file_results": file_results
            }
        }
        
        all_model_results.append(model_result)
    
    # Sort by F1 score descending
    all_model_results.sort(key=lambda x: x["f1_score"], reverse=True)
    return all_model_results


def main():
    # Define paths
    project_root = Path(__file__).parent.parent
    predictions_dir = project_root / "predictions"
    output_path = project_root / "docs" / "results.json"
    
    # Default shot count for the leaderboard (2 as per requirements)
    shot_filter = 2
    
    print(f"Collecting results from {predictions_dir} (shot filter: {shot_filter})")
    
    # Collect model results
    model_results = collect_model_results(predictions_dir, shot_filter=shot_filter)
    
    if not model_results:
        print("Warning: No model results found")
        return
    
    print(f"Found {len(model_results)} models")
    for model in model_results:
        file_count = len(model["details"].get("file_results", []))
        print(f"  {model['model_name']}: {file_count} files, {model['shots']}-shot, F1: {model['f1_score']:.4f}")
    
    # Save to the output file
    with open(output_path, "w") as f:
        json.dump(model_results, f, indent=2)
    
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()