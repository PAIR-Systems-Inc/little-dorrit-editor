"""Prediction generation for the Little Dorrit Editor benchmark."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import openai
from rich.console import Console

from little_dorrit_editor.config import get_model
from little_dorrit_editor.prompt import (
    create_few_shot_prompt,
    create_zero_shot_prompt,
    load_examples
)
from little_dorrit_editor.utils import extract_json_from_llm_response


def generate_predictions(
    image_path: Path,
    output_path: Path,
    model_id: str = "gpt-4o",
    shots: int = 0,
    sample_dataset_path: Optional[Path] = None,
    temperature: float = 0.1,
    console: Optional[Console] = None
) -> Dict[str, Any]:
    """Generate predictions using a model.
    
    Args:
        image_path: Path to the image file to analyze
        output_path: Path to save the predicted edits JSON
        model_id: Model ID from configuration
        shots: Number of examples to use for few-shot prompting
        sample_dataset_path: Path to the sample dataset for few-shot examples
        temperature: Model temperature parameter
        console: Rich console for output (creates a new one if None)
        
    Returns:
        The predictions dictionary
        
    Raises:
        FileNotFoundError: If the image file doesn't exist
        ValueError: If attempting to use evaluation data for examples
    """
    # Set up console
    if console is None:
        console = Console()
    
    # Validate image path
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Load examples for few-shot prompting if requested
    examples = []
    if shots > 0 and sample_dataset_path is not None:
        # Check if sample dataset exists
        if not sample_dataset_path.exists():
            console.print(
                f"[yellow]Warning:[/yellow] Sample dataset not found: {sample_dataset_path}. "
                "Falling back to zero-shot prompting."
            )
        else:
            # Safety check: Ensure the dataset path is from sample data
            if 'eval' in str(sample_dataset_path).lower():
                raise ValueError(
                    "CRITICAL SAFETY ERROR: Attempted to use evaluation data for examples. "
                    "This is not allowed to prevent data leakage. Use sample data only."
                )
            
            # Load examples
            console.print(f"Loading {shots} examples from {sample_dataset_path}...")
            examples = load_examples(sample_dataset_path, num_examples=shots)
            console.print(f"Loaded {len(examples)} examples for few-shot prompting.")
    
    # Create prompt
    if examples:
        console.print(f"Creating {len(examples)}-shot prompt...")
        messages = create_few_shot_prompt(str(image_path), examples)
    else:
        console.print("Creating zero-shot prompt...")
        messages = create_zero_shot_prompt(str(image_path))
    
    # Get model configuration
    model_config = get_model(model_id)
    
    # Initialize the client with the appropriate base URL and API key
    client_params = {"api_key": model_config.api_key}
    if model_config.endpoint:
        client_params["base_url"] = model_config.endpoint
    client = openai.Client(**client_params)
    
    # Call the model
    console.print(f"Calling {model_config.logical_name} to generate predictions...")
    response = client.chat.completions.create(
        model=model_config.model_name,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    
    console.print("[dim]Raw response received, extracting JSON...[/dim]")
    
    # Parse the response with graceful error handling
    try:
        predictions = extract_json_from_llm_response(response.choices[0].message.content)
        edits = predictions.get("edits", [])
        error_message = None
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Could not parse JSON from model response: {str(e)}")
        console.print("[yellow]Creating empty prediction with error information[/yellow]")
        edits = []
        error_message = f"Failed to parse model output as JSON: {str(e)[:200]}..."
    
    # Create the full prediction with metadata
    full_prediction = {
        "image": image_path.name,
        "page_number": 1,  # Default, should be extracted from filename ideally
        "source": "Little Dorrit",
        "edits": edits,
        "annotator": model_config.logical_name,
        "annotation_date": datetime.now().isoformat(),
        "verified": False
    }
    
    # Add error information if parsing failed
    if error_message:
        full_prediction["error"] = error_message
        full_prediction["raw_response"] = response.choices[0].message.content[:1000]  # First 1000 chars for diagnosis
    
    # Save the predictions
    with open(output_path, "w") as f:
        json.dump(full_prediction, f, indent=2)
    
    console.print(f"[green]Predictions saved to {output_path}[/green]")
    
    # Show different messages based on success/failure
    if error_message:
        console.print(f"[yellow]Warning: No edits found due to JSON parsing error[/yellow]")
    else:
        console.print(f"Found {len(edits)} edits.")
    
    return full_prediction