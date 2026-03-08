"""Prompt generation and example management for Little Dorrit Editor."""

import json
import random
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import base64
from datasets import load_from_disk
from PIL import Image


JPEG_QUALITY_MIN = 60
JPEG_QUALITY_MAX = 100
MAX_RESIZE_PASSES = 12

try:
    RESAMPLING_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLING_LANCZOS = Image.LANCZOS


def _guess_mime_type(image_path: str) -> str:
    suffix = Path(image_path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _prepare_for_jpeg(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image

    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, "white")
        alpha = image.convert("RGBA")
        background.paste(alpha, mask=alpha.getchannel("A"))
        return background

    return image.convert("RGB")


def _render_jpeg_bytes(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        subsampling=0,
    )
    return buffer.getvalue()


def _resize_image_to_fit_bytes(image_path: str, max_bytes: int) -> tuple[bytes, str]:
    with Image.open(image_path) as source_image:
        image = _prepare_for_jpeg(source_image.copy())

    best_bytes: Optional[bytes] = None
    low = 0.1
    high = 1.0

    for _ in range(MAX_RESIZE_PASSES):
        scale = (low + high) / 2
        if scale >= 0.999:
            resized = image
        else:
            resized = image.resize(
                (
                    max(1, int(round(image.width * scale))),
                    max(1, int(round(image.height * scale))),
                ),
                RESAMPLING_LANCZOS,
            )

        best_quality_bytes: Optional[bytes] = None
        q_low = JPEG_QUALITY_MIN
        q_high = JPEG_QUALITY_MAX

        while q_low <= q_high:
            quality = (q_low + q_high) // 2
            candidate = _render_jpeg_bytes(resized, quality)

            if len(candidate) <= max_bytes:
                best_quality_bytes = candidate
                q_low = quality + 1
            else:
                q_high = quality - 1

        if best_quality_bytes is not None:
            best_bytes = best_quality_bytes
            low = scale
        else:
            high = scale

    if best_bytes is None:
        raise ValueError(f"Could not fit image within {max_bytes} bytes: {image_path}")

    return best_bytes, "image/jpeg"


def encode_image_for_prompt(image_path: str, max_bytes: Optional[int] = None) -> Dict[str, str]:
    """Encode an image as a data URL for inclusion in prompts.

    Args:
        image_path: Path to the image file
        max_bytes: Optional byte budget for the encoded image payload

    Returns:
        A dictionary containing the mime type and base64-encoded image bytes
    """
    mime_type = _guess_mime_type(image_path)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    if max_bytes is not None and len(image_bytes) > max_bytes:
        image_bytes, mime_type = _resize_image_to_fit_bytes(image_path, max_bytes)

    return {
        "mime_type": mime_type,
        "base64": base64.b64encode(image_bytes).decode("utf-8"),
    }


def create_image_message_part(image_path: str, max_bytes: Optional[int] = None) -> Dict[str, Any]:
    """Create an OpenAI-compatible image content part for a prompt."""
    encoded_image = encode_image_for_prompt(image_path, max_bytes=max_bytes)
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{encoded_image['mime_type']};base64,{encoded_image['base64']}"
        }
    }


def get_example_prompt(
    example: Dict[str, Any],
    image_max_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """Format a dataset example as a prompt.

    Args:
        example: A dataset example with image and annotations
        image_max_bytes: Optional byte budget applied to each image in the prompt

    Returns:
        A dictionary with the formatted prompt and system message
    """
    # Get the image
    image_path = example["image"]

    # Create the user message with the image
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Please identify all handwritten editorial corrections in this printed text and output them as JSON."
            },
            create_image_message_part(image_path, max_bytes=image_max_bytes),
        ]
    }

    # Create the assistant message with the edits
    assistant_message = {
        "role": "assistant",
        "content": json.dumps({"edits": example["edits"]}, indent=2)
    }

    return {"user": user_message, "assistant": assistant_message}


def load_examples(
    dataset_path: Path,
    num_examples: int = 3,
    image_max_bytes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Load examples from the Hugging Face dataset.

    Args:
        dataset_path: Path to the Hugging Face dataset
        num_examples: Number of examples to load
        image_max_bytes: Optional byte budget applied to example images

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
    prompt_examples = [
        get_example_prompt(example, image_max_bytes=image_max_bytes)
        for example in examples
    ]

    return prompt_examples


def create_few_shot_prompt(
    image_path: str,
    examples: List[Dict[str, Any]],
    image_max_bytes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Create a few-shot prompt for the model.

    Args:
        image_path: Path to the image to analyze
        examples: List of examples in prompt format
        image_max_bytes: Optional byte budget applied to each image in the prompt

    Returns:
        A list of messages for the API call
    """
    # Start with the system message
    messages = [
        {
            "role": "system",
            "content": """
You are an expert editor tasked with identifying handwritten editorial
corrections on printed text pages.

Your job is to identify all handwritten markups and corrections on the page and
convert them to structured JSON output.

Create a SEPARATE edit entry for EACH individual correction, even if multiple
corrections occur in the same sentence or phrase. DO NOT combine multiple edits
into a single edit entry.

For each individual correction, identify:
1. The type of edit (insertion, deletion, replacement, punctuation,
   capitalization, italicize)
2. The original text being modified (keep this minimal - only include the
   specific text being changed)
3. The corrected text after applying the edit (only include the specific text
   affected by this one change)
4. The line number where the edit occurs (line 0 is the title, line 1 is the
   first full line of body text)
5. The page identifier.

OUTPUT FORMAT:
{
  "edits": [
    {
      "type": "insertion | deletion | replacement | punctuation | capitalization | italicize",
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
- replacement: Substituting text with alternatives (both original and corrected
  text differ)
- punctuation: Modifying or adding punctuation marks (each punctuation mark
  added/changed is a separate edit)
- capitalization: Changing case (upper/lower)
- italicize: Changing text to italic.

Look for handwritten markups such as:
- Caret marks (^) indicating insertions
- Strikethroughs indicating deletions
- Circled text or underlining indicating replacements
- Added or modified punctuation
- Markup for capitalization changes

Examples of properly separated edits:
1. For a sentence with multiple punctuation changes:
   Instead of one edit: "My dog ran fast and barked" → "My dog ran fast, and barked."
   Create two edits:
     - "fast and" → "fast, and" (punctuation)
     - "barked" → "barked." (punctuation)

Be precise about the line numbers. Count from 1 for the first full line of body text.
Titles and headings are line 0."""
        }
    ]

    # Add examples in alternating user/assistant format
    for example in examples:
        messages.append(example["user"])
        messages.append(example["assistant"])

    # Add the actual question
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Please identify all handwritten editorial corrections in this printed text and output them as JSON."
            },
            create_image_message_part(image_path, max_bytes=image_max_bytes),
        ]
    })

    return messages


def create_zero_shot_prompt(
    image_path: str,
    image_max_bytes: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Create a zero-shot prompt for the model.

    Args:
        image_path: Path to the image to analyze
        image_max_bytes: Optional byte budget applied to the image in the prompt

    Returns:
        A list of messages for the API call
    """
    # Use the same function but with no examples
    return create_few_shot_prompt(
        image_path,
        examples=[],
        image_max_bytes=image_max_bytes,
    )
