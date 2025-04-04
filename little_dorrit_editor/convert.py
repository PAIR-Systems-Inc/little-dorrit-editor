"""Convert local annotations to a Hugging Face dataset."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from datasets import Dataset, Features, Image, Value, Sequence
from PIL import Image as PILImage
from rich.console import Console
from rich.progress import Progress, TaskID

from little_dorrit_editor.types import EditAnnotation


def load_annotations(data_dir: Path) -> List[Dict]:
    """Load all annotation JSON files from a directory.

    Args:
        data_dir: Directory containing annotation files

    Returns:
        List of loaded annotations
    """
    console = Console()
    annotations = []
    
    json_files = list(data_dir.glob("*.json"))
    console.print(f"Found {len(json_files)} JSON annotation files")
    
    with Progress() as progress:
        task = progress.add_task("Loading annotations...", total=len(json_files))
        
        for json_path in json_files:
            with open(json_path, "r") as f:
                try:
                    data = json.load(f)
                    # Validate the annotation format
                    annotation = EditAnnotation.model_validate(data)
                    
                    # Check if corresponding image exists - could be .jpg, .png, etc.
                    image_name = data.get("image")
                    image_path = data_dir / image_name
                    if not image_path.exists():
                        console.print(
                            f"[yellow]Warning:[/yellow] Missing image {image_name} for {json_path.name}"
                        )
                        progress.advance(task)
                        continue
                    
                    # Add validated data to the list
                    annotations.append(annotation.model_dump())
                    
                except Exception as e:
                    console.print(
                        f"[red]Error:[/red] Failed to parse {json_path.name}: {str(e)}"
                    )
            
            progress.advance(task)
    
    return annotations


def create_hf_dataset(
    data_dir: Path, output_dir: Path, dataset_name: str = "little-dorrit-editor"
) -> Dataset:
    """Create a Hugging Face dataset from annotation files.

    Args:
        data_dir: Directory containing annotation files and images
        output_dir: Output directory for the dataset
        dataset_name: Name of the dataset

    Returns:
        Created Hugging Face dataset
    """
    console = Console()
    console.print(f"Creating Hugging Face dataset from {data_dir}")
    
    # Load all annotations
    annotations = load_annotations(data_dir)
    
    # Create dataset entries
    dataset_entries = []
    
    with Progress() as progress:
        task = progress.add_task("Processing entries...", total=len(annotations))
        
        for annotation in annotations:
            image_name = annotation["image"]
            image_path = data_dir / image_name
            
            if not image_path.exists():
                progress.advance(task)
                continue
            
            # Create entry
            entry = {
                "image": str(image_path),  # Dataset will load this as PIL image
                "edits": annotation["edits"],
                "page_number": annotation["page_number"],
                "source": annotation["source"],
            }
            
            # Add optional fields if they exist
            for field in ["annotator", "annotation_date", "verified"]:
                if field in annotation and annotation[field] is not None:
                    entry[field] = annotation[field]
            
            dataset_entries.append(entry)
            progress.advance(task)
    
    # Create the dataset without specifying features (let them be inferred)
    dataset = Dataset.from_list(dataset_entries)
    
    # Save to disk
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset.save_to_disk(output_dir / dataset_name)
    
    # Create dataset card
    create_dataset_card(output_dir / dataset_name / "README.md", len(dataset_entries))
    
    console.print(
        f"[green]Dataset created successfully![/green] Saved to {output_dir / dataset_name}"
    )
    console.print(f"Total examples: {len(dataset_entries)}")
    
    return dataset


def create_dataset_card(output_path: Path, example_count: int) -> None:
    """Create a README.md file for the dataset.

    Args:
        output_path: Path to save the README
        example_count: Number of examples in the dataset
    """
    content = f"""---
annotations_creators:
  - expert-annotated
language_creators:
  - found
languages:
  - en
licenses:
  - mit
multilinguality:
  - monolingual
size_categories:
  - {'10K<n<100K' if example_count > 10000 else '1K<n<10K' if example_count > 1000 else 'n<1K'}
source_datasets:
  - original
task_categories:
  - text-editing
task_ids:
  - multimodal-editing
---

# Little Dorrit Editor

The Little Dorrit Editor dataset contains {example_count} annotated pages from Charles Dickens' novel "Little Dorrit" with handwritten editorial corrections. It is designed to benchmark multimodal language models on their ability to interpret handwritten markup on printed text.

## Dataset Description

Each example contains:
- An image of a printed page with handwritten markup/corrections
- Ground truth annotations of the editorial changes
- Page number and source information
- Optional metadata about the annotator

The editorial changes include:
- Insertions
- Deletions
- Replacements
- Punctuation changes
- Capitalization changes
- Text reordering

### Line Numbering Convention

- Line numbers start at 1 for the first full line of body text on the page
- The chapter name (e.g., "Chapter II") is not counted as a line
- The chapter title or section title (e.g., "Fellow Travellers") is referred to as line 0
- This ensures consistent reference to editable text while still allowing markup of titles and headings

## Usage

This dataset is intended to be used with the Little Dorrit Editor benchmark, which provides evaluation scripts and a leaderboard for comparing model performance.

```python
from datasets import load_dataset

# Load from Hugging Face
dataset = load_dataset("yourusername/little-dorrit-editor")

# Or load from local directory
dataset = load_dataset("path/to/dataset")

# Access an example
example = dataset["train"][0]
image = example["image"]  # PIL Image
edits = example["edits"]  # List of edit operations
```

For more details, visit the [Little Dorrit Editor repository](https://github.com/yourusername/little-dorrit-editor).
"""
    
    with open(output_path, "w") as f:
        f.write(content)