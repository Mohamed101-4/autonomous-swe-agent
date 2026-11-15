"""Patcher: asks the LLM for a fix and applies it to the workspace."""

from __future__ import annotations

import difflib
from pathlib import Path

from swe_agent.llm import LLM, LLMError, extract_json
from swe_agent.state import AgentState

SYSTEM = """You are the patching agent in a bug-fixing team. Fix the bug with the smallest \
correct change to the source code. Do not edit tests.
Reply with one JSON object only:
  {"explanation": "<one or two sentences>",
   "edits": [{"path": "<file path>", "search": "<exact existing text>", "replace": "<new text>"}]}
Rules: "search" must be copied exactly from the file, including indentation, and must appear \
exactly once in that file. Keep each search block short but unique."""


class PatchError(ValueError):
    pass


def apply_edits(workspace: Path, edits: list[dict], originals: dict[str, str]) -> str:
    """Apply search/replace edits in place and return a unified diff vs. `originals`.

    `originals` maps path -> original contents; files touched for the first time are added.
    """
    root = workspace.resolve()
    new_contents: dict[str, str] = {}
    for edit in edits:
        rel = str(edit.get("path", "")).strip()
        target = (root / rel).resolve()
        if not rel or root not in target.parents or not target.is_file():
            raise PatchError(f"bad path in edit: {rel!r}")
        if rel not in originals:
            originals[rel] = target.read_text()
        text = new_contents.get(rel, originals[rel])
        search, replace = edit.get("search", ""), edit.get("replace", "")
        count = text.count(search) if search else 0
        if count != 1:
            raise PatchError(f"search text found {count} times in {rel} (must be exactly once)")
        new_contents[rel] = text.replace(search, replace, 1)

    diff_parts = []
    for rel, text in new_contents.items():
        (root / rel).write_text(text)
        diff_parts.extend(
            difflib.unified_diff(
                originals[rel].splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
    return "".join(diff_parts)


def restore_originals(workspace: Path, originals: dict[str, str]) -> None:
    for rel, text in originals.items():
        (workspace / rel).write_text(text)


def build_prompt(state: AgentState) -> str:
    plan = state.get("plan") or {}
    parts = [f"Bug report:\n{state['issue']}"]
    if plan.get("hypotheses"):
        parts.append("Planner hypotheses:\n" + "\n".join(f"- {h}" for h in plan["hypotheses"]))
    parts.append("Relevant code:")
    for c in state.get("candidates", []):
        parts.append(f"--- {c['path']} lines {c['start_line']}-{c['end_line']} ---\n{c['source']}")
    if state.get("feedback"):
        parts.append(
            "Your previous patch did not work. Previous diff:\n"
            f"{state.get('diff') or '(none applied)'}\n\nFeedback:\n{state['feedback']}"
        )
    return "\n\n".join(parts)


class Patcher:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def __call__(self, state: AgentState) -> AgentState:
        workspace = Path(state["workspace_path"])
        originals = dict(state.get("original_files") or {})
        restore_originals(workspace, originals)  # each attempt starts from the original code
        attempts = state.get("attempts", 0) + 1
        log = list(state.get("log", []))

        edits: list[dict] = []
        try:
            reply = extract_json(self.llm.complete(SYSTEM, build_prompt(state)))
            edits = list(reply.get("edits") or [])
            if not edits:
                raise PatchError("the model returned no edits")
            diff = apply_edits(workspace, edits, originals)
        except (PatchError, LLMError) as exc:
            restore_originals(workspace, originals)
            log.append(f"patcher: attempt {attempts} failed to produce a patch: {exc}")
            return {
                "attempts": attempts,
                "edits": edits,
                "diff": "",
                "original_files": originals,
                "patch_error": str(exc),
                "status": "patch_failed",
                "log": log,
            }

        log.append(f"patcher: attempt {attempts}: {reply.get('explanation', '').strip()}")
        return {
            "attempts": attempts,
            "edits": edits,
            "diff": diff,
            "original_files": originals,
            "patch_error": None,
            "status": "patched",
            "log": log,
        }
