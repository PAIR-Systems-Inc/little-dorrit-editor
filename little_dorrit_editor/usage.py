"""Provider-reported inference usage. Unknown quantities stay null, never zero."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def number(*values: Any) -> int | float | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value) and value >= 0:
                return value
    return None


def normalize_usage(response: Any) -> dict:
    """Normalize Chat Completions/Responses usage, retaining provider details.

    Input includes cached and image tokens when the provider includes them.
    Reasoning is a subset of output, not an additional charge to add to output.
    Native Anthropic input excludes cache hits/writes; include those explicitly.
    """
    raw = as_dict(getattr(response, "usage", None))
    if isinstance(response, dict):
        raw = as_dict(response.get("usage"))
    prompt = as_dict(raw.get("prompt_tokens_details") or raw.get("input_tokens_details"))
    completion = as_dict(raw.get("completion_tokens_details") or raw.get("output_tokens_details"))
    input_tokens = number(raw.get("prompt_tokens"), raw.get("input_tokens"))
    cached = number(prompt.get("cached_tokens"), raw.get("cache_read_input_tokens"))
    cache_write = number(prompt.get("cache_write_tokens"), raw.get("cache_creation_input_tokens"))
    if input_tokens is not None and "prompt_tokens" not in raw and "cache_read_input_tokens" in raw:
        input_tokens += (cached or 0) + (cache_write or 0)
    output_tokens = number(raw.get("completion_tokens"), raw.get("output_tokens"))
    reasoning = number(completion.get("reasoning_tokens"), raw.get("reasoning_tokens"))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": number(raw.get("total_tokens"),
                               input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None),
        "input_image_tokens": number(prompt.get("image_tokens"), raw.get("input_image_tokens")),
        "input_audio_tokens": number(prompt.get("audio_tokens")),
        "cached_input_tokens": cached,
        "cache_write_input_tokens": cache_write,
        "reasoning_tokens": reasoning,
        "answer_tokens": output_tokens - reasoning if output_tokens is not None and reasoning is not None and output_tokens >= reasoning else None,
        "provider_cost_usd": number(raw.get("cost")),
        "raw": raw,
    }


def append_usage_attempt(output_path: Path, record: dict) -> None:
    """Keep an append-only audit across retries and manual reruns of a page.

    A subdirectory keeps these records out of prediction/evaluation file globs.
    Prompts, images, credentials, and response text are never logged here.
    """
    directory = output_path.parent / "usage"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{output_path.stem}.jsonl").open("a") as stream:
        stream.write(json.dumps({"recorded_at": datetime.now(timezone.utc).isoformat(), **record}) + "\n")
