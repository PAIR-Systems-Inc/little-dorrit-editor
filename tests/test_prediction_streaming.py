"""Long-running streamed answers must remain complete and auditable."""
from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletionChunk

from little_dorrit_editor.predict import IncompletePredictionStream, _collect_stream
from little_dorrit_editor.usage import normalize_usage


def chunk(content=None, finish=None, **extra):
    return ChatCompletionChunk.model_validate({
        "id": "gen-test", "model": "google/test", "created": 1,
        "object": "chat.completion.chunk", "provider": "Google",
        "choices": [{"index": 0, "delta": {"content": content},
                     "finish_reason": finish}], **extra,
    })


def client_for(chunks):
    client = MagicMock()
    client.chat.completions.create.return_value = nullcontext(iter(chunks))
    return client


@pytest.mark.parametrize("empty_choices", [True, False])
def test_stream_joins_answer_and_retains_final_usage(empty_choices):
    usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
             "completion_tokens_details": {"reasoning_tokens": 40}, "cost": .01}
    final = {"usage": usage}
    if empty_choices:
        final["choices"] = []
    reasoning = chunk()
    reasoning.choices[0].delta.model_extra["reasoning"] = "not answer text"
    client = client_for([reasoning, chunk('{"edits":'), chunk('[]}', "stop"),
                         chunk("", "stop", **final)])
    response = _collect_stream(client, {"model": "google/test", "messages": []})
    assert response.choices[0].message.content == '{"edits":[]}'
    assert response.provider == "Google"
    assert normalize_usage(response)["provider_cost_usd"] == .01
    assert normalize_usage(response)["reasoning_tokens"] == 40
    assert client.chat.completions.create.call_args.kwargs["stream"] is True


@pytest.mark.parametrize("finish", [None, "length", "content_filter"])
def test_stream_rejects_incomplete_even_if_text_is_valid_json(finish):
    with pytest.raises(ValueError, match="Incomplete prediction stream"):
        _collect_stream(client_for([chunk('{"edits":[]}', finish)]), {})


def test_stream_rejects_provider_error_after_text():
    with pytest.raises(ValueError, match="Provider streaming error"):
        _collect_stream(client_for([
            chunk('{"edits":[]}', "stop"),
            chunk(error={"code": 504, "message": "A Timeout Occurred"}),
        ]), {})


def test_truncated_stream_keeps_billable_usage_for_retry_audit():
    usage = {"prompt_tokens": 100, "completion_tokens": 32768,
             "total_tokens": 32868, "cost": .33}
    with pytest.raises(IncompletePredictionStream) as error:
        _collect_stream(client_for([chunk("", "length", usage=usage)]), {})
    assert error.value.metadata["id"] == "gen-test"
    assert normalize_usage(error.value.metadata)["provider_cost_usd"] == .33
