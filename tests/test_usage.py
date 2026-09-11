"""Usage must retain unknowns and retry charges without double-counting tokens."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from little_dorrit_editor.usage import normalize_usage
from little_dorrit_editor.predict import generate_predictions
from little_dorrit_editor.types import EditAnnotation


def test_usage_preserves_provider_breakdown_without_double_counting():
    raw = {"prompt_tokens": 1000, "completion_tokens": 300, "total_tokens": 1300,
           "prompt_tokens_details": {"cached_tokens": 400, "image_tokens": 200},
           "completion_tokens_details": {"reasoning_tokens": 250}, "cost": .0123,
           "cost_details": {"upstream_inference_cost": .01}}
    usage = normalize_usage({"usage": raw})
    assert usage["input_tokens"] == 1000
    assert usage["total_tokens"] == 1300
    assert usage["reasoning_tokens"] == 250
    assert usage["answer_tokens"] == 50
    assert usage["input_image_tokens"] == 200
    assert usage["cached_input_tokens"] == 400
    assert usage["provider_cost_usd"] == .0123
    assert usage["raw"] == raw


def test_usage_unknown_is_not_free():
    usage = normalize_usage({"usage": {"prompt_tokens": 80, "completion_tokens": 10}})
    assert usage["total_tokens"] == 90
    for key in ["input_image_tokens", "cached_input_tokens", "reasoning_tokens", "answer_tokens", "provider_cost_usd"]:
        assert usage[key] is None
    assert normalize_usage({"usage": {"cost": 0}})["provider_cost_usd"] == 0
    assert normalize_usage({"usage": {"cost": float("nan")}})["provider_cost_usd"] is None


def test_responses_and_native_anthropic_cache_semantics():
    usage = normalize_usage({"usage": {"input_tokens": 50, "output_tokens": 10,
                                       "input_tokens_details": {"cached_tokens": 20},
                                       "output_tokens_details": {"reasoning_tokens": 0}}})
    assert usage["input_tokens"] == 50
    assert usage["answer_tokens"] == 10
    native = normalize_usage({"usage": {"input_tokens": 50, "output_tokens": 10,
                                        "cache_read_input_tokens": 20, "cache_creation_input_tokens": 30}})
    assert native["input_tokens"] == 100
    assert native["total_tokens"] == 110


@pytest.mark.parametrize("content,status", [('{"edits": []}', "success"), ('bad json', "parse_error")])
def test_prediction_logs_usage_on_success_and_bad_json(tmp_path, monkeypatch, content, status):
    from little_dorrit_editor import predict
    config = SimpleNamespace(image_max_bytes=None, logical_name="Test", reasoning_effort=None,
                             model_name="test", supports_temperature=True, api_key="not-a-real-key",
                             endpoint="https://example.test/v1", request_timeout_seconds=None,
                             supports_json_object_response=True, service_tier=None,
                             openrouter_provider=None, openrouter_reasoning=None, max_tokens=None)
    monkeypatch.setattr(predict, "get_model", lambda _: config)
    monkeypatch.setattr(predict, "create_zero_shot_prompt", lambda *a, **k: [])
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                               usage={"prompt_tokens": 100, "completion_tokens": 20, "cost": .5}, id="request-1", model="test")
    client = MagicMock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr(predict.openai, "Client", lambda **kwargs: client)
    image = tmp_path / "page.png"
    image.touch()
    output = tmp_path / "003_01_20260911_prediction.json"
    for _ in range(2):
        result = generate_predictions(image, output, model_id="test", console=MagicMock())
    assert result["inference"]["usage"]["provider_cost_usd"] == .5
    assert result["inference"]["status"] == status
    assert EditAnnotation.model_validate(result).inference == result["inference"]
    attempts = [json.loads(line) for line in (tmp_path / "usage" / f"{output.stem}.jsonl").read_text().splitlines()]
    assert len(attempts) == 2
    assert sum(a["usage"]["provider_cost_usd"] for a in attempts) == 1
    assert "not-a-real-key" not in json.dumps(attempts)


def test_api_retry_attempts_are_retained_even_when_final_call_fails(tmp_path, monkeypatch):
    from little_dorrit_editor import predict
    config = SimpleNamespace(image_max_bytes=None, logical_name="Test", reasoning_effort=None,
                             model_name="test", supports_temperature=True, api_key="not-a-real-key",
                             endpoint="https://example.test/v1", request_timeout_seconds=None,
                             supports_json_object_response=True, service_tier=None,
                             openrouter_provider=None, openrouter_reasoning=None, max_tokens=None)
    monkeypatch.setattr(predict, "get_model", lambda _: config)
    monkeypatch.setattr(predict, "create_zero_shot_prompt", lambda *a, **k: [])
    monkeypatch.setattr(predict, "_should_retry_api_error", lambda _: True)
    monkeypatch.setattr(predict.time, "sleep", lambda _: None)
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("Failed")
    monkeypatch.setattr(predict.openai, "Client", lambda **kwargs: client)
    image = tmp_path / "page.png"
    image.touch()
    output = tmp_path / "003_01_20260911_prediction.json"
    with pytest.raises(RuntimeError):
        generate_predictions(image, output, model_id="test", console=MagicMock())
    attempts = [json.loads(line) for line in (tmp_path / "usage" / f"{output.stem}.jsonl").read_text().splitlines()]
    assert [a["attempt"] for a in attempts] == [1, 2, 3]
    assert all(a["status"] == "api_error" and a["usage"] is None for a in attempts)
    assert not output.exists()
