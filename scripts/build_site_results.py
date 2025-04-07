#!/usr/bin/env python
"""
Build results.json for the website based on predictions directory structure.

This script collects raw data from individual result files in prediction directories
and consolidates them into a single JSON file for client-side processing and display
on the leaderboard site. No metrics are calculated server-side - all metric calculation
is deferred to the JavaScript client.
"""

import json
import datetime
from pathlib import Path
import glob
import re
from typing import Dict, List, Any, Optional

from little_dorrit_editor.types import EditMatch, EvaluationResult


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
    """Load a single results file without calculating any metrics.
    
    Args:
        filepath: Path to the results file
    
    Returns:
        Raw JSON data from the file
    """
    with open(filepath, "r") as f:
        data = json.load(f)
    
    # If this is the new format with details as a list of EditMatch objects,
    # ensure all objects are dictionaries (not Pydantic models)
    if isinstance(data.get("details", {}), list):
        # Convert edit match objects to dictionaries if they're not already
        edit_matches = []
        for match in data["details"]:
            if isinstance(match, dict):
                edit_matches.append(match)
            else:
                edit_matches.append(match.dict())
        
        # Update the details field with the dictionary versions
        data["details"] = edit_matches
    
    return data


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
    """Collect results for all models in the predictions directory without calculating metrics.
    
    Args:
        predictions_dir: Path to the predictions directory
        shot_filter: If provided, only include models with this shot count
    
    Returns:
        List of model results with raw data for client-side processing
    """
    all_model_results = []
    
    # Find all model directories
    model_dirs = [d for d in predictions_dir.iterdir() if d.is_dir()]
    
    for model_dir in model_dirs:
        model_name = model_dir.name
        
        # Check for .noinclude file - standard marker to exclude from leaderboard
        if (model_dir / ".noinclude").exists():
            print(f"Skipping {model_name}: found .noinclude marker")
            continue
        
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
        
        # Check if display_name is provided in config
        display_name = config.get("display_name", model_name)
        
        # If no display_name in config, format model name nicely
        if display_name == model_name and re.match(r"^[a-z0-9-]+$", model_name):
            # Special case for GPT models
            if model_name.startswith("gpt"):
                parts = model_name.split("-")
                if len(parts) > 1:
                    # Preserve all hyphens in the name
                    display_name = parts[0].upper()  # "GPT"
                    for i in range(1, len(parts)):
                        display_name += f"-{parts[i]}"  # Keep hyphens between components
            else:
                # Capitalize first letter of each word
                display_name = " ".join(word.capitalize() for word in model_name.replace("-", " ").split())
        
        # Check if we have annotator information from the result files
        annotator = None
        annotation_date = None
        
        # Try to get annotator info from first file with that field
        for fr in file_results:
            if fr.get("annotator"):
                annotator = fr.get("annotator")
                break
        
        # Try to get annotation date from first file with that field
        for fr in file_results:
            if fr.get("annotation_date"):
                annotation_date = fr.get("annotation_date")
                break
        
        # Create the model result entry - without calculating any metrics
        model_result = {
            "model_name": display_name,
            "model_id": model_name,  # Include original model ID
            "date": latest_date.isoformat() if latest_date else datetime.datetime.now().isoformat(),
            "shots": config.get("shots", 2),  # Include shot count
            "config": config,  # Include full configuration
            "annotator": annotator,  # Include annotator if available
            "annotation_date": annotation_date,  # Include annotation date if available
            "file_results": file_results  # Include all raw file results for client-side processing
        }
        
        all_model_results.append(model_result)
    
    # Sort alphabetically by model name instead of by metrics
    all_model_results.sort(key=lambda x: x["model_name"])
    return all_model_results


def main():
    # Define paths
    project_root = Path(__file__).parent.parent
    predictions_dir = project_root / "predictions"
    output_path = project_root / "docs" / "results.json"
    
    # Default shot count for the leaderboard (2 as per requirements)
    shot_filter = 2
    
    print(f"Collecting results from {predictions_dir} (shot filter: {shot_filter})")
    
    # Collect raw model results without calculating metrics
    model_results = collect_model_results(predictions_dir, shot_filter=shot_filter)
    
    if not model_results:
        print("Warning: No model results found")
        return
    
    print(f"Found {len(model_results)} models")
    for model in model_results:
        file_count = len(model["file_results"])
        print(f"  {model['model_name']}: {file_count} files, {model['shots']}-shot")
    
    # Save to the output file
    with open(output_path, "w") as f:
        json.dump(model_results, f, indent=2)
    
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()