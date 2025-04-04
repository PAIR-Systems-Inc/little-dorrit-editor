#!/usr/bin/env python
"""
Script to reorganize the predictions directory structure.

This script moves files from the old structure to the new structure:
- predictions/MODEL/eval/ -> predictions/MODEL/predictions/eval/
- predictions/MODEL/sample/ -> predictions/MODEL/predictions/sample/
- predictions/MODEL/results/ -> predictions/MODEL/results/

It also creates a config.json file for each model with metadata about the experiment.
"""

import os
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


def extract_shot_count(filename: str) -> Optional[int]:
    """Try to guess the shot count from a filename.
    Always returns 2 for now since that's our default."""
    return 2  # Default to 2 shots as mentioned in the requirements


def create_config_file(model_dir: Path, shot_count: int) -> None:
    """Create a config.json file with metadata about the experiment.

    Args:
        model_dir: Path to the model directory
        shot_count: Number of shots used for the experiment
    """
    config = {
        "model_name": model_dir.name,
        "shots": shot_count,
        "temperature": 0.0,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes": f"Benchmark run with {shot_count}-shot learning"
    }
    
    config_path = model_dir / "config.json"
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Created config file: {config_path}")


def reorganize_model_directory(model_dir: Path) -> None:
    """Reorganize a single model directory.
    
    Args:
        model_dir: Path to the model directory
    """
    # Get all subdirectories
    subdirs = [d for d in model_dir.iterdir() if d.is_dir()]
    
    # Create new directory structure
    predictions_dir = model_dir / "predictions"
    predictions_dir.mkdir(exist_ok=True)
    
    # Move files and directories
    moved_files = 0
    
    # Check for evaluation predictions
    eval_dir = model_dir / "eval"
    if eval_dir.exists() and eval_dir.is_dir():
        new_eval_dir = predictions_dir / "eval"
        new_eval_dir.mkdir(exist_ok=True)
        
        # Move prediction files
        for file in eval_dir.glob("*_prediction.json"):
            shutil.move(str(file), str(new_eval_dir / file.name))
            moved_files += 1
    
    # Check for sample predictions
    sample_dir = model_dir / "sample"
    if sample_dir.exists() and sample_dir.is_dir():
        new_sample_dir = predictions_dir / "sample"
        new_sample_dir.mkdir(exist_ok=True)
        
        # Move prediction files
        for file in sample_dir.glob("*_prediction.json"):
            shutil.move(str(file), str(new_sample_dir / file.name))
            moved_files += 1
    
    # No need to move results directory as it's already in the correct place,
    # but create subdirectories if they don't exist
    results_dir = model_dir / "results"
    if results_dir.exists() and results_dir.is_dir():
        eval_results_dir = results_dir / "eval"
        eval_results_dir.mkdir(exist_ok=True)
        
        sample_results_dir = results_dir / "sample"
        sample_results_dir.mkdir(exist_ok=True)
        
        # Move result files to the appropriate subdirectory
        for file in results_dir.glob("*_results.json"):
            # Determine if this is a sample or eval file
            file_id = file.stem.split("_")[0]
            
            # Check if file is from eval (003-008) or sample (001-002)
            if file_id in ["001", "002"]:
                shutil.move(str(file), str(sample_results_dir / file.name))
            else:
                shutil.move(str(file), str(eval_results_dir / file.name))
            moved_files += 1
    
    # Check if any old directories are now empty and remove them
    for old_dir in [eval_dir, sample_dir]:
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
            print(f"Removed empty directory: {old_dir}")
    
    # Try to determine the shot count from the files or use the default
    shot_count = extract_shot_count(model_dir.name)
    
    # Create the config file
    create_config_file(model_dir, shot_count)
    
    print(f"Reorganized {model_dir.name}: moved {moved_files} files")


def main():
    """Main function to reorganize the predictions directory structure."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    predictions_dir = project_root / "predictions"
    
    if not predictions_dir.exists():
        print(f"Error: Predictions directory not found: {predictions_dir}")
        return
    
    # Get all model directories
    model_dirs = [d for d in predictions_dir.iterdir() if d.is_dir()]
    
    if not model_dirs:
        print("No model directories found.")
        return
    
    print(f"Found {len(model_dirs)} model directories.")
    
    # Reorganize each model directory
    for model_dir in model_dirs:
        print(f"Reorganizing {model_dir.name}...")
        reorganize_model_directory(model_dir)
    
    print("Directory reorganization complete.")


if __name__ == "__main__":
    main()