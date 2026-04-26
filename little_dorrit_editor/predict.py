"""Prediction generation for the Little Dorrit Editor benchmark."""

import json
import time
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


def _should_retry_api_error(exc: Exception) -> bool:
    """Return True for transient API failures worth retrying."""
    if isinstance(exc, json.JSONDecodeError):
        return True

    if isinstance(exc, (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)):
        return True

    if isinstance(exc, openai.APIStatusError):
        return exc.status_code in {408, 409, 429} or exc.status_code >= 500

    return False


def _normalize_message_content(content: Any) -> Optional[str]:
    """Normalize provider-specific message content into a plain string."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                if isinstance(text_value, dict) and isinstance(text_value.get("value"), str):
                    parts.append(text_value["value"])
                    continue

            item_text = getattr(item, "text", None)
            if isinstance(item_text, str):
                parts.append(item_text)
            elif isinstance(item_text, dict) and isinstance(item_text.get("value"), str):
                parts.append(item_text["value"])

        normalized = "\n".join(part for part in parts if part).strip()
        return normalized or None

    return None


def generate_predictions(
    image_path: Path,
    output_path: Path,
    model_id: str = "gpt-4o",
    shots: int = 0,
    sample_dataset_path: Optional[Path] = None,
    temperature: float = 0.1,
    reasoning_effort: Optional[str] = None,
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
        reasoning_effort: Reasoning effort for thinking models (e.g. low/medium/high)
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

    # Get model configuration early so prompt construction can honor any
    # model-specific image constraints.
    model_config = get_model(model_id)
    image_max_bytes = model_config.image_max_bytes

    if image_max_bytes is not None:
        console.print(
            f"Applying a per-image payload cap of {image_max_bytes:,} bytes "
            f"for {model_config.logical_name}."
        )
    
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
            examples = load_examples(
                sample_dataset_path,
                num_examples=shots,
                image_max_bytes=image_max_bytes,
            )
            console.print(f"Loaded {len(examples)} examples for few-shot prompting.")
    
    # Create prompt
    if examples:
        console.print(f"Creating {len(examples)}-shot prompt...")
        messages = create_few_shot_prompt(
            str(image_path),
            examples,
            image_max_bytes=image_max_bytes,
        )
    else:
        console.print("Creating zero-shot prompt...")
        messages = create_zero_shot_prompt(
            str(image_path),
            image_max_bytes=image_max_bytes,
        )

    # Prefer the explicit parameter, but fall back to the model's configured default.
    effort = reasoning_effort if reasoning_effort is not None else model_config.reasoning_effort
    effort_norm = effort.strip().lower() if isinstance(effort, str) else None
    is_thinking = bool(effort_norm) and effort_norm != "none"

    # GPT-5 family does not accept the temperature parameter at all.
    is_gpt5_family = model_config.model_name.startswith("gpt-5")
    supports_temperature = (
        model_config.supports_temperature
        if model_config.supports_temperature is not None
        else True
    )
    
    # Initialize the client with the appropriate base URL and API key
    client_params = {"api_key": model_config.api_key}
    if model_config.endpoint:
        client_params["base_url"] = model_config.endpoint
    client = openai.Client(**client_params)
    
    # Call the model
    console.print(f"Calling {model_config.logical_name} to generate predictions...")
    supports_json_object_response = (
        model_config.supports_json_object_response
        if model_config.supports_json_object_response is not None
        else "anthropic.com" not in model_config.endpoint
    )
    create_kwargs: Dict[str, Any] = {
        "model": model_config.model_name,
        "messages": messages,
    }

    if supports_json_object_response:
        create_kwargs["response_format"] = {"type": "json_object"}

    if model_config.service_tier:
        create_kwargs["service_tier"] = model_config.service_tier

    if model_config.openrouter_provider:
        create_kwargs.setdefault("extra_body", {})["provider"] = model_config.openrouter_provider

    if model_config.openrouter_reasoning:
        create_kwargs.setdefault("extra_body", {})["reasoning"] = model_config.openrouter_reasoning

    if model_config.max_tokens is not None:
        create_kwargs["max_tokens"] = model_config.max_tokens

    if is_thinking:
        create_kwargs["reasoning_effort"] = effort_norm

    if is_gpt5_family or is_thinking or not supports_temperature:
        # Don't send temperature when it's not supported.
        # If the caller provided one, tell them we're ignoring it.
        if temperature is not None:
            console.print(
                "[yellow]Warning:[/yellow] temperature is not supported for this model/mode; ignoring."
            )
    else:
        create_kwargs["temperature"] = temperature

    response = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(**create_kwargs)
            break
        except Exception as exc:
            if attempt == max_attempts or not _should_retry_api_error(exc):
                raise

            backoff_seconds = 2 ** (attempt - 1)
            console.print(
                "[yellow]Warning:[/yellow] API call failed "
                f"({type(exc).__name__}: {exc}). Retrying in {backoff_seconds}s..."
            )
            time.sleep(backoff_seconds)
    
    console.print("[dim]Raw response received, extracting JSON...[/dim]")

    message_content = None
    raw_response_excerpt = None
    try:
        message_content = _normalize_message_content(response.choices[0].message.content)
    except (AttributeError, IndexError, TypeError):
        message_content = None

    try:
        raw_response_excerpt = response.model_dump_json(indent=2)[:1000]
    except Exception:
        raw_response_excerpt = None
    
    # Parse the response with graceful error handling
    try:
        if not message_content:
            raise ValueError("Model returned empty or non-text content")

        predictions = extract_json_from_llm_response(message_content)
        edits = predictions.get("edits", [])
        error_message = None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
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
        full_prediction["raw_response"] = (
            message_content[:1000]
            if message_content
            else raw_response_excerpt
        )
    
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
