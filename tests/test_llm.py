import pytest

from swe_agent.config import load_settings
from swe_agent.llm import AnthropicLLM, FakeLLM, LLMError, extract_json


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```\nDone') == {"a": 1}
    assert extract_json('Here: {"b": [1, 2]} ok') == {"b": [1, 2]}
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_fake_llm_replays_and_records():
    llm = FakeLLM(["first", lambda prompt: prompt.upper()])
    assert llm.complete("sys", "hi") == "first"
    assert llm.complete("sys", "hi") == "HI"
    assert len(llm.calls) == 2
    with pytest.raises(LLMError):
        llm.complete("sys", "again")


def test_anthropic_llm_requires_key():
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        AnthropicLLM(load_settings(env={}))


def test_anthropic_llm_request_and_reply_parsing():
    """Exercise the real SDK against a fake HTTP server (no network, no real key)."""
    import json

    import anthropic
    import httpx2 as httpx

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": '{"ok": true}'}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 11, "output_tokens": 5},
            },
        )

    client = anthropic.Anthropic(
        api_key="test-not-a-real-key",
        base_url="http://fake-anthropic.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    settings = load_settings(env={"ANTHROPIC_API_KEY": "test-not-a-real-key"})
    llm = AnthropicLLM(settings, client=client)

    assert llm.complete("system text", "user text") == '{"ok": true}'
    assert seen["url"].endswith("/v1/messages")
    assert seen["body"]["model"] == "claude-opus-5-5"
    assert seen["body"]["system"] == "system text"
    assert seen["body"]["output_config"] == {"effort": "medium"}
    assert seen["body"]["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert (llm.usage.calls, llm.usage.input_tokens, llm.usage.output_tokens) == (1, 11, 5)
