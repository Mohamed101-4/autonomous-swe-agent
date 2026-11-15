"""Evaluation helpers: load the bug set and grade a patched workspace with hidden tests."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from swe_agent.test_runner import TestRun, TestRunner

DEFAULT_BUGS_DIR = Path(__file__).resolve().parents[1] / "eval" / "bugs"


@dataclass(frozen=True)
class Bug:
    id: str
    issue: str
    repo: Path  # what the agent sees (visible tests only)
    hidden_tests: Path  # used only for grading
    reference_edits: list[dict]


def load_bugs(bugs_dir: Path | str = DEFAULT_BUGS_DIR, ids: list[str] | None = None) -> list[Bug]:
    bugs = []
    for meta_path in sorted(Path(bugs_dir).glob("*/bug.json")):
        meta = json.loads(meta_path.read_text())
        if ids and meta["id"] not in ids:
            continue
        base = meta_path.parent
        bugs.append(
            Bug(
                id=meta["id"],
                issue=meta["issue"],
                repo=(base / meta.get("repo", "repo")).resolve(),
                hidden_tests=base / "hidden",
                reference_edits=meta["reference_edits"],
            )
        )
    if ids and len(bugs) != len(set(ids)):
        missing = set(ids) - {b.id for b in bugs}
        raise ValueError(f"unknown bug ids: {sorted(missing)}")
    return bugs


def grade(workspace: Path | str, bug: Bug, runner: TestRunner) -> TestRun:
    """Run visible + hidden tests on a copy of the patched workspace.

    The agent never sees the hidden tests, so passing them is the real success check.
    """
    with tempfile.TemporaryDirectory(prefix="grade-") as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(workspace, copy)
        for test_file in bug.hidden_tests.glob("test_*.py"):
            shutil.copy(test_file, copy / "tests" / test_file.name)
        return runner.run(copy)


# ---------------------------------------------------------------------------
# Running configurations and summarizing results
# ---------------------------------------------------------------------------

# USD per million tokens (input, output), Anthropic first-party list prices
# (from the claude-api reference cached 2026-11-03). Used only for cost reports.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

CONFIGS: dict[str, dict] = {
    "multi_agent": {},
    "baseline": {"baseline": True},
    "no_embeddings": {"use_embeddings": False},
    "reduced_planning": {"planning_depth": "reduced"},
    "minimal_feedback": {"feedback_mode": "minimal"},
    "no_retries": {"max_retries": 0},
}


def run_one(bug: Bug, config: str, *, settings, llm, runner, embedder, workspace_root):
    """Run one configuration on one bug and grade it with the hidden tests."""
    from swe_agent.baseline import run_baseline
    from swe_agent.pipeline import RunOptions, run_agent

    spec = dict(CONFIGS[config])
    if spec.pop("baseline", False):
        result = run_baseline(
            bug.repo, bug.issue, settings=settings, llm=llm, runner=runner,
            workspace_root=workspace_root,
        )  # fmt: skip
    else:
        options = RunOptions(**spec)
        result = run_agent(
            bug.repo, bug.issue, settings=settings, llm=llm, runner=runner,
            embedder=embedder if options.use_embeddings else None, options=options,
            workspace_root=workspace_root,
        )  # fmt: skip
    result.mode = config
    graded = grade(result.workspace, bug, runner)
    return result, graded


def make_record(bug_id: str, config: str, repeat: int, result, graded, error: str | None) -> dict:
    usage = (result.llm_usage if result else {}) or {}
    return {
        "config": config,
        "bug": bug_id,
        "repeat": repeat,
        "agent_verdict": result.status if result else "error",
        "resolved": bool(graded and graded.ok),  # hidden + visible tests pass
        "attempts": result.attempts if result else 0,
        "duration_s": result.duration_s if result else None,
        "hidden_passed": graded.passed if graded else None,
        "hidden_failed": (graded.failed + graded.errors) if graded else None,
        "llm_calls": usage.get("calls", 0),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "diff": result.diff if result else "",
        "error": error,
    }


def summarize(records: list[dict], model: str) -> dict[str, dict]:
    import statistics

    price = PRICES.get(model)
    out: dict[str, dict] = {}
    for config in dict.fromkeys(r["config"] for r in records):
        rows = [r for r in records if r["config"] == config]
        times = [r["duration_s"] for r in rows if r["duration_s"] is not None]
        said_pass = [r for r in rows if r["agent_verdict"] == "resolved"]
        tok_in = sum(r["input_tokens"] for r in rows)
        tok_out = sum(r["output_tokens"] for r in rows)
        out[config] = {
            "runs": len(rows),
            "resolved": sum(r["resolved"] for r in rows),
            "resolve_rate": round(sum(r["resolved"] for r in rows) / len(rows), 3),
            "errors": sum(r["error"] is not None for r in rows),
            "mean_time_s": round(statistics.mean(times), 2) if times else None,
            "median_time_s": round(statistics.median(times), 2) if times else None,
            "mean_attempts": round(statistics.mean(r["attempts"] for r in rows), 2),
            # How often the verifier's PASS/FAIL verdict matches the hidden-test grade.
            "validation_accuracy": round(
                sum((r["agent_verdict"] == "resolved") == r["resolved"] for r in rows) / len(rows),
                3,
            ),
            # Of the patches the verifier accepted, how many really pass hidden tests.
            "verifier_pass_precision": (
                round(sum(r["resolved"] for r in said_pass) / len(said_pass), 3)
                if said_pass
                else None
            ),
            "llm_calls": sum(r["llm_calls"] for r in rows),
            "input_tokens": tok_in,
            "output_tokens": tok_out,
            "cost_usd": round((tok_in * price[0] + tok_out * price[1]) / 1e6, 4) if price else None,
        }
    return out


def summary_markdown(summary: dict[str, dict], meta: dict) -> str:
    lines = [
        "# Eval results",
        "",
        f"- Date: {meta['date']}  |  git commit: `{meta['git_commit']}`",
        f"- Model: `{meta['model']}` (effort `{meta['effort']}`)  |  sandbox: {meta['sandbox']}",
        f"- Machine: {meta['machine']}",
        f"- {meta.get('dataset', 'Bugs')}: {meta['n_bugs']}  |  repeats: {meta['repeats']}",
        "",
        "| config | resolved | rate | mean time (s) | mean attempts | validation acc. "
        "| verifier PASS precision | LLM calls | cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for config, s in summary.items():
        lines.append(
            f"| {config} | {s['resolved']}/{s['runs']} | {s['resolve_rate']:.0%} "
            f"| {s['mean_time_s']} | {s['mean_attempts']} | {s['validation_accuracy']:.0%} "
            f"| {s['verifier_pass_precision']} | {s['llm_calls']} | {s['cost_usd']} |"
        )
    lines += [
        "",
        "Resolved = the patched repo passes the visible tests and the hidden tests the agent "
        "never saw. Validation accuracy = share of runs where the agent's own PASS/FAIL "
        "verdict matched that hidden-test result.",
    ]
    return "\n".join(lines) + "\n"
