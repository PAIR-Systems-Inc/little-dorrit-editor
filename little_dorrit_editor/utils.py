"""Utility functions for Little Dorrit Editor."""

import json
import re
from typing import Dict


def extract_json_from_llm_response(response_text: str) -> Dict:
    """Extract JSON from LLM response text, handling various formats.

    Args:
        response_text: The raw text response from an LLM

    Returns:
        Parsed JSON as a dictionary

    Raises:
        json.JSONDecodeError: If the response cannot be parsed as JSON
    """
    # First, check if the entire response is already valid JSON
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Look for code blocks with or without language specifier
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    code_blocks = re.findall(code_block_pattern, response_text)

    if code_blocks:
        # Try each code block until one works
        for block in code_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # If no code blocks or none worked, try to find anything that looks like JSON
    # (between curly braces)
    json_pattern = r"\{[\s\S]*\}"
    json_matches = re.findall(json_pattern, response_text)

    if json_matches:
        for match in json_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    # If all else fails, raise an error with the original response
    raise json.JSONDecodeError(
        f"Could not extract valid JSON from response: {response_text[:3000]}...",
        response_text, 0
    )