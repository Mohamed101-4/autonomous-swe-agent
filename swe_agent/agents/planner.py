"""Planner: reads the issue and decides what to look for."""

from __future__ import annotations

from pathlib import Path

from swe_agent.code_index import iter_python_files
from swe_agent.llm import LLM, extract_json
from swe_agent.retrieval import tokenize
from swe_agent.state import AgentState

SYSTEM = """You are the planning agent in a bug-fixing team. Read a bug report and a list of \
files in a Python repo, then decide what the team should investigate. Do not write a fix.
Reply with one JSON object only, with these keys:
  "summary": one sentence restating the bug,
  "hypotheses": list of likely causes (short strings),
  "search_terms": list of words or identifiers to search the code for,
  "suspect_symbols": list of function/class names that probably contain the bug,
  "steps": list of short investigation steps."""


def heuristic_plan(issue: str) -> dict:
    """Plan without an LLM: just use the issue's keywords."""
    terms = list(dict.fromkeys(tokenize(issue)))
    return {
        "summary": issue,
        "hypotheses": [],
        "search_terms": terms,
        "suspect_symbols": [],
        "steps": ["Search the code for the issue's keywords"],
    }


class Planner:
    """depth="full" asks the LLM for a plan; depth="reduced" uses keywords only (ablation)."""

    def __init__(self, llm: LLM | None, depth: str = "full", max_files: int = 200) -> None:
        if depth not in ("full", "reduced"):
            raise ValueError(f"unknown planning depth: {depth}")
        self.llm, self.depth, self.max_files = llm, depth, max_files

    def __call__(self, state: AgentState) -> AgentState:
        issue = state["issue"]
        if self.depth == "reduced" or self.llm is None:
            plan = heuristic_plan(issue)
        else:
            repo = Path(state.get("workspace_path") or state["repo_path"])
            files = [p.relative_to(repo).as_posix() for p in iter_python_files(repo)]
            prompt = f"Bug report:\n{issue}\n\nPython files in the repo:\n" + "\n".join(
                files[: self.max_files]
            )
            plan = heuristic_plan(issue) | extract_json(self.llm.complete(SYSTEM, prompt))
        for key in ("hypotheses", "search_terms", "suspect_symbols", "steps"):
            plan[key] = [str(x) for x in plan.get(key) or []]
        log = list(state.get("log", []))
        log.append(f"planner: {plan['summary']}")
        log += [f"planner:   step: {s}" for s in plan["steps"]]
        return {"plan": plan, "status": "planned", "log": log}
