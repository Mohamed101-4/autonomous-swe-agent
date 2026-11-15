"""Offline demo: the real pipeline with a SCRIPTED LLM (no API key, no model).

The replies below were written by hand for examples/buggy_app. They exist so
anyone can watch the whole pipeline run (planner, AST/RAG localizer, patcher,
Docker verifier, retry, Postgres) without an API key. They show the plumbing
works, not that a model can fix the bug.
"""

from __future__ import annotations

import json
from pathlib import Path

from swe_agent.llm import FakeLLM

DEMO_REPO = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"
DEMO_ISSUE = "Login crashes when email is missing"

# A plan, then a first patch that only half-fixes the bug (so the verifier's
# feedback and the retry loop are exercised), then a correct patch.
PLAN_REPLY = json.dumps(
    {
        "summary": "login() raises when the email field is missing",
        "hypotheses": ["login indexes data['email'] without checking it exists"],
        "search_terms": ["login", "email"],
        "suspect_symbols": ["login"],
        "steps": ["Read login() in app/auth.py", "Check how email is read"],
    }
)
BAD_PATCH = json.dumps(
    {
        "explanation": "Use .get (still crashes on None).",
        "edits": [
            {
                "path": "app/auth.py",
                "search": 'email = normalize_email(data["email"])',
                "replace": 'email = normalize_email(data.get("email", ""))',
            }
        ],
    }
)
GOOD_PATCH = json.dumps(
    {
        "explanation": "Return an error when email is missing or empty.",
        "edits": [
            {
                "path": "app/auth.py",
                "search": '    email = normalize_email(data["email"])\n',
                "replace": (
                    '    email = data.get("email")\n'
                    "    if not email:\n"
                    '        return LoginResult(ok=False, error="email is required")\n'
                    "    email = normalize_email(email)\n"
                ),
            }
        ],
    }
)


def scripted_llm() -> FakeLLM:
    return FakeLLM([PLAN_REPLY, BAD_PATCH, GOOD_PATCH])
