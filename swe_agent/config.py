"""Settings loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MODEL = "claude-opus-5-5"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    model: str
    effort: str
    database_url: str | None
    sandbox_image: str
    sandbox_timeout_seconds: int
    sandbox_memory: str
    sandbox_cpus: float
    max_patch_retries: int

    @property
    def has_llm_key(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings(env: dict[str, str] | None = None, use_dotenv: bool = True) -> Settings:
    """Build Settings from `env` (defaults to os.environ, after loading .env)."""
    if env is None:
        if use_dotenv:
            load_dotenv()
        env = dict(os.environ)

    return Settings(
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        model=env.get("ANTHROPIC_MODEL") or DEFAULT_MODEL,
        effort=env.get("ANTHROPIC_EFFORT") or "medium",
        database_url=env.get("DATABASE_URL") or None,
        sandbox_image=env.get("SANDBOX_IMAGE") or "python:3.12-slim",
        sandbox_timeout_seconds=int(env.get("SANDBOX_TIMEOUT_SECONDS") or 120),
        sandbox_memory=env.get("SANDBOX_MEMORY") or "512m",
        sandbox_cpus=float(env.get("SANDBOX_CPUS") or 1.0),
        max_patch_retries=int(env.get("MAX_PATCH_RETRIES") or 2),
    )
