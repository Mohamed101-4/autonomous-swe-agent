"""Verifier: runs the tests on the patched workspace and judges the result."""

from __future__ import annotations

from pathlib import Path

from swe_agent.state import AgentState
from swe_agent.test_runner import TestRun, TestRunner

MAX_FEEDBACK_LINES = 60


def make_feedback(run: TestRun, mode: str) -> str:
    """mode="full": failing tests + output tail; mode="minimal": pass/fail only (ablation)."""
    if mode == "minimal":
        return "The tests still fail."
    tail = "\n".join(run.output.strip().splitlines()[-MAX_FEEDBACK_LINES:])
    failing = "\n".join(f"- {t}" for t in run.failing_tests) or "(none listed)"
    timeout = " (timed out)" if run.timed_out else ""
    return (
        f"pytest exit code {run.exit_code}{timeout}: {run.passed} passed, "
        f"{run.failed} failed, {run.errors} errors.\nFailing tests:\n{failing}\n\n"
        f"Output (last lines):\n{tail}"
    )


class Verifier:
    def __init__(self, runner: TestRunner, feedback_mode: str = "full") -> None:
        if feedback_mode not in ("full", "minimal"):
            raise ValueError(f"unknown feedback mode: {feedback_mode}")
        self.runner, self.feedback_mode = runner, feedback_mode

    def __call__(self, state: AgentState) -> AgentState:
        log = list(state.get("log", []))
        if state.get("patch_error"):
            log.append("verifier: no patch to test")
            return {
                "feedback": f"Your patch could not be applied: {state['patch_error']}",
                "status": "failed",
                "log": log,
            }

        run = self.runner.run(Path(state["workspace_path"]))
        log.append(
            f"verifier: {run.passed} passed, {run.failed} failed, {run.errors} errors "
            f"in {run.duration_s:.2f}s -> {'PASS' if run.ok else 'FAIL'}"
        )
        return {
            "test_result": run.to_dict(),
            "feedback": None if run.ok else make_feedback(run, self.feedback_mode),
            "status": "resolved" if run.ok else "failed",
            "log": log,
        }
