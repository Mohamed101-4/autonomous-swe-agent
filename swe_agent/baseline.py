"""Single-agent baseline: one LLM call with whole files as context, one test run, no retries.

No planner, no AST/embedding localization, no verifier feedback loop. Files are
picked by simple BM25 file ranking until a character budget is used up (for the
small eval repos this means the whole non-test source).
"""

from __future__ import annotations

import time
from pathlib import Path

from swe_agent.agents import Patcher, Verifier
from swe_agent.code_index import iter_python_files
from swe_agent.config import Settings, load_settings
from swe_agent.llm import LLM, AnthropicLLM
from swe_agent.pipeline import (
    DEFAULT_WORKSPACE_ROOT,
    RunResult,
    llm_usage,
    make_runner,
    new_workspace,
)
from swe_agent.retrieval import BM25, tokenize
from swe_agent.test_runner import TestRunner

TEST_DIRS = {"tests", "test"}


def select_files(repo: Path, issue: str, max_chars: int) -> list[dict]:
    files = [
        p
        for p in iter_python_files(repo)
        if not (TEST_DIRS & set(p.relative_to(repo).parts[:-1])) and p.stat().st_size > 0
    ]
    texts = [p.read_text(errors="replace") for p in files]
    rels = [p.relative_to(repo).as_posix() for p in files]
    scores = BM25([tokenize(r) * 3 + tokenize(t) for r, t in zip(rels, texts, strict=True)]).scores(
        tokenize(issue)
    )
    chosen, used = [], 0
    for i in sorted(range(len(files)), key=lambda i: -scores[i]):
        if used + len(texts[i]) > max_chars:
            continue
        used += len(texts[i])
        n_lines = texts[i].count("\n") + 1
        chosen.append(
            {"path": rels[i], "qualname": "(whole file)", "kind": "file", "start_line": 1,
             "end_line": n_lines, "score": round(float(scores[i]), 3), "source": texts[i]}
        )  # fmt: skip
    return chosen


def run_baseline(
    repo: Path | str,
    issue: str,
    *,
    settings: Settings | None = None,
    llm: LLM | None = None,
    runner: TestRunner | None = None,
    sandbox: str = "docker",
    workspace_root: Path | str = DEFAULT_WORKSPACE_ROOT,
    max_context_chars: int = 60_000,
    test_targets: list[str] | None = None,
) -> RunResult:
    settings = settings or load_settings()
    llm = llm or AnthropicLLM(settings)
    runner = runner or make_runner(settings, sandbox)

    start = time.monotonic()
    workspace = new_workspace(repo, workspace_root)
    candidates = select_files(workspace, issue, max_context_chars)
    state = {
        "issue": issue,
        "repo_path": str(Path(repo).resolve()),
        "workspace_path": str(workspace.resolve()),
        "candidates": candidates,
        "attempts": 0,
        "test_targets": test_targets,
        "log": [f"baseline: gave the model {len(candidates)} whole file(s)"],
    }
    state |= Patcher(llm)(state)
    state |= Verifier(runner)(state)
    state["log"].append(f"report: {state['status']} after 1 patch attempt(s)")
    return RunResult(
        issue=issue,
        repo=state["repo_path"],
        status="resolved" if state["status"] == "resolved" else "failed",
        attempts=state["attempts"],
        duration_s=round(time.monotonic() - start, 3),
        relevant_files=[c["path"] for c in candidates],
        candidates=candidates,
        diff=state.get("diff", ""),
        test_result=state.get("test_result", {}),
        log=state["log"],
        workspace=str(workspace),
        mode="baseline",
        llm_usage=llm_usage(llm),
    )
