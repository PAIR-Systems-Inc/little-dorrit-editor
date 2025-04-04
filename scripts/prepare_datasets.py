#!/usr/bin/env python3
"""
Utility script to prepare Little Dorrit Editor datasets.

This script converts all data directories to Hugging Face format in one go.
It's designed to regenerate the datasets on demand and should not be committed to git.
"""

import sys
import shutil
from pathlib import Path

# Add parent directory to path so we can import the little_dorrit_editor package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from little_dorrit_editor.convert import create_hf_dataset
from rich.console import Console

console = Console()


def prepare_datasets(
    output_dir: Path = Path("data/hf"),
    clean: bool = False,
    dataset_name: str = "little-dorrit-editor",
):
    """Prepare all datasets.
    
    Args:
        output_dir: Base directory for output
        clean: Whether to clean the output directory first
        dataset_name: Name of the dataset
    """
    # Configure paths
    sample_dir = project_root / "data" / "sample"
    eval_dir = project_root / "data" / "eval"

    # Create output directories
    output_dir = project_root / output_dir
    sample_output = output_dir / "sample"
    eval_output = output_dir / "eval"

    # Clean if requested
    if clean and output_dir.exists():
        console.print(f"Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir, ignore_errors=True)

    # Create sample dataset
    if sample_dir.exists():
        console.print(f"Creating sample dataset from: {sample_dir}")
        create_hf_dataset(
            data_dir=sample_dir,
            output_dir=sample_output,
            dataset_name=dataset_name,
        )
    else:
        console.print(f"[yellow]Warning:[/yellow] Sample directory not found: {sample_dir}")

    # Create eval dataset if it exists
    if eval_dir.exists():
        console.print(f"Creating evaluation dataset from: {eval_dir}")
        create_hf_dataset(
            data_dir=eval_dir,
            output_dir=eval_output,
            dataset_name=dataset_name,
        )
    else:
        console.print(f"[yellow]Warning:[/yellow] Evaluation directory not found: {eval_dir}")

    console.print("[green]Datasets prepared successfully![/green]")
    console.print(f"Sample dataset: {sample_output / dataset_name}")
    console.print(f"Evaluation dataset: {eval_output / dataset_name}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare Little Dorrit Editor datasets")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/hf"),
        help="Base directory for output (default: data/hf)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean the output directory before creating datasets",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="little-dorrit-editor",
        help="Name of the dataset (default: little-dorrit-editor)",
    )

    args = parser.parse_args()
    prepare_datasets(
        output_dir=args.output_dir,
        clean=args.clean,
        dataset_name=args.dataset_name,
    )