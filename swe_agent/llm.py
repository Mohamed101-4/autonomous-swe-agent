"""Small LLM interface: a real Anthropic client and a scripted fake for tests."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from swe_agent.config import Settings


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicLLM:
    """Calls Claude through the official Anthropic SDK."""

    def __init__(self, settings: Settings, max_tokens: int = 16000) -> None:
        import anthropic

        if not settings.has_llm_key:
            raise LLMError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.model
        self.effort = settings.effort
        self.max_tokens = max_tokens
        self.usage = Usage()

    def complete(self, system: str, prompt: str) -> str:
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": self.effort},
            # If a safety classifier declines, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        self.usage.calls += 1
        self.usage.input_tokens += response.usage.input_tokens
        self.usage.output_tokens += response.usage.output_tokens
        if response.stop_reason == "refusal":
            raise LLMError("The model declined this request.")
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            raise LLMError("The model's answer was cut off (max_tokens reached).")
        return text


@dataclass
class FakeLLM:
    """Returns scripted replies, in order. Replies can be strings or functions of the prompt."""

    replies: list[str | Callable[[str], str]]
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        if not self.replies:
            raise LLMError("FakeLLM ran out of scripted replies")
        reply = self.replies.pop(0)
        return reply(prompt) if callable(reply) else reply


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply (tolerates ```json fences and prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    if start != -1:
        candidates.append(text[start : text.rfind("}") + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise LLMError(f"Could not find a JSON object in the model reply: {text[:200]!r}")
