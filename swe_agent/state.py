"""Shared state passed between the agents (and later, LangGraph nodes)."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    issue: str
    repo_path: str  # original repo (never modified)
    workspace_path: str  # isolated copy the patcher edits
    plan: dict[str, Any]
    candidates: list[dict[str, Any]]  # code snippets picked by the localizer
    relevant_files: list[str]
    edits: list[dict[str, str]]
    diff: str
    original_files: dict[str, str]  # file contents before any patch, for resets
    patch_error: str | None
    test_result: dict[str, Any]
    feedback: str | None  # verifier feedback for the next patch attempt
    attempts: int
    status: str  # "planned" | "localized" | "patched" | "resolved" | "failed"
    log: list[str]
