"""Prompt generation and example management for Little Dorrit Editor."""

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from datasets import load_from_disk
from PIL import Image
import base64
from io import BytesIO


def encode_image_to_base64(image_path: str) -> str:
    """Encode an image to base64 for inclusion in prompts.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded image
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    return encoded_image


def get_example_prompt(example: Dict[str, Any]) -> Dict[str, Any]:
    """Format a dataset example as a prompt.

    Args:
        example: A dataset example with image and annotations

    Returns:
        A dictionary with the formatted prompt and system message
    """
    # Get the image
    image_path = example["image"]
    encoded_image = encode_image_to_base64(image_path)

    # Create the user message with the image
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Please identify all handwritten editorial corrections in this printed text and output them as JSON."
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encoded_image}"
                }
            }
        ]
    }

    # Create the assistant message with the edits
    assistant_message = {
        "role": "assistant",
        "content": json.dumps({"edits": example["edits"]}, indent=2)
    }

    return {"user": user_message, "assistant": assistant_message}


def load_examples(dataset_path: Path, num_examples: int = 3) -> List[Dict[str, Any]]:
    """Load examples from the Hugging Face dataset.

    Args:
        dataset_path: Path to the Hugging Face dataset
        num_examples: Number of examples to load

    Returns:
        List of examples in prompt format

    Raises:
        ValueError: If the dataset path contains 'eval' to prevent data leakage
    """
    # Safety check: Ensure we're not using evaluation data for examples
    if 'eval' in str(dataset_path).lower():
        raise ValueError(
            "CRITICAL SAFETY ERROR: Attempted to use evaluation data for few-shot examples. "
            "Only sample data should be used for examples to prevent data leakage."
        )

    # Load the dataset
    dataset = load_from_disk(dataset_path)

    # Select random examples
    if len(dataset) <= num_examples:
        examples = dataset
    else:
        indices = random.sample(range(len(dataset)), num_examples)
        examples = [dataset[i] for i in indices]

    # Convert examples to prompt format
    prompt_examples = [get_example_prompt(example) for example in examples]

    return prompt_examples


def create_few_shot_prompt(image_path: str, examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create a few-shot prompt for the model.

    Args:
        image_path: Path to the image to analyze
        examples: List of examples in prompt format

    Returns:
        A list of messages for the API call
    """
    # Start with the system message
    messages = [
        {
            "role": "system",
            "content": """You are an expert editor tasked with identifying handwritten editorial corrections on printed text pages.

Your job is to identify all handwritten markups and corrections on the page and convert them to structured JSON output.

EXTREMELY IMPORTANT: Create a SEPARATE edit entry for EACH individual correction, even if multiple corrections occur in the same sentence or phrase. DO NOT combine multiple edits into a single edit entry.

For each individual correction, identify:
1. The type of edit (insertion, deletion, replacement, punctuation, capitalization, reordering)
2. The original text being modified (keep this minimal - only include the specific text being changed)
3. The corrected text after applying the edit (only include the specific text affected by this one change)
4. The line number where the edit occurs (line 0 is the title, line 1 is the first full line of body text)
5. The page identifier

OUTPUT FORMAT:
{
  "edits": [
    {
      "type": "insertion | deletion | replacement | punctuation | capitalization | reordering",
      "original_text": "the text before the edit",
      "corrected_text": "the text after the edit",
      "line_number": <integer>,
      "page": "page_identifier"
    },
    ...
  ]
}

EDIT TYPES:
- insertion: Adding new text (original doesn't contain the added text)
- deletion: Removing text (corrected doesn't contain the removed text)
- replacement: Substituting text with alternatives (both original and corrected text differ)
- punctuation: Modifying or adding punctuation marks (each punctuation mark added/changed is a separate edit)
- capitalization: Changing case (upper/lower)
- reordering: Rearranging text sequence

Look for handwritten markups such as:
- Caret marks (^) indicating insertions
- Strikethroughs indicating deletions
- Circled text or underlining indicating replacements
- Added or modified punctuation
- Markup for capitalization changes
- Arrows or numbering indicating text reordering

Examples of properly separated edits:
1. For a sentence with multiple punctuation changes:
   Instead of one edit: "My dog ran fast and barked" → "My dog ran fast, and barked."
   Create two edits: 
     - "fast and" → "fast, and" (punctuation)
     - "barked" → "barked." (punctuation)

2. For text with both punctuation and capitalization changes:
   Instead of one edit: "hello world" → "Hello, world!"
   Create three edits:
     - "hello" → "Hello" (capitalization)
     - "world" → "world," (punctuation)
     - "world," → "world!" (punctuation)

Be precise about the line numbers. Count from 1 for the first full line of body text.
Titles and headings are line 0."""
        }
    ]

    # Add examples in alternating user/assistant format
    for example in examples:
        messages.append(example["user"])
        messages.append(example["assistant"])

    # Add the actual question
    encoded_image = encode_image_to_base64(image_path)
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Please identify all handwritten editorial corrections in this printed text and output them as JSON."
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encoded_image}"
                }
            }
        ]
    })

    return messages


def create_zero_shot_prompt(image_path: str) -> List[Dict[str, Any]]:
    """Create a zero-shot prompt for the model.

    Args:
        image_path: Path to the image to analyze

    Returns:
        A list of messages for the API call
    """
    # Use the same function but with no examples
    return create_few_shot_prompt(image_path, examples=[])