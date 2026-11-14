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
