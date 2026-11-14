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
