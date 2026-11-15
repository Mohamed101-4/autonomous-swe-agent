"""Run a repo's pytest suite and parse the results.

LocalPytestRunner runs on the host (used in Phase 2 and unit tests).
A Docker sandbox runner with the same interface is added in Phase 3.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

_COUNT_RE = re.compile(r"(\d+) (passed|failed|errors?|skipped)")
_FAILED_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)


@dataclass
class TestRun:
    __test__ = False  # not a pytest test class

    exit_code: int
    passed: int
    failed: int
    errors: int
    duration_s: float
    output: str
    failing_tests: list[str]
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0 and self.passed > 0

    def to_dict(self) -> dict:
        return asdict(self) | {"ok": self.ok}


def parse_pytest_output(output: str, exit_code: int, duration_s: float) -> TestRun:
    counts = {"passed": 0, "failed": 0, "errors": 0}
    lines = output.strip().splitlines()
    summary = next((ln for ln in reversed(lines) if _COUNT_RE.search(ln)), "")
    for number, word in _COUNT_RE.findall(summary):
        key = "errors" if word.startswith("error") else word
        if key in counts:
            counts[key] = int(number)
    return TestRun(
        exit_code=exit_code,
        duration_s=round(duration_s, 3),
        output=output,
        failing_tests=_FAILED_RE.findall(output),
        **counts,
    )


class TestRunner(Protocol):
    def run(self, workspace: Path) -> TestRun: ...


class LocalPytestRunner:
    """Runs pytest on the host with the current Python. Not sandboxed."""

    def __init__(self, timeout_s: int = 120) -> None:
        self.timeout_s = timeout_s

    def run(self, workspace: Path) -> TestRun:
        cmd = [sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=workspace, capture_output=True, text=True, timeout=self.timeout_s
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else exc.stdout
            run = parse_pytest_output(out or "", 124, time.monotonic() - start)
            run.timed_out = True
            return run
        return parse_pytest_output(
            proc.stdout + proc.stderr, proc.returncode, time.monotonic() - start
        )
