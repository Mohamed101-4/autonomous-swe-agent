"""Run a repo's pytest suite and parse the results.

LocalPytestRunner runs on the host (used in Phase 2 and unit tests).
A Docker sandbox runner with the same interface is added in Phase 3.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
import uuid
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


SANDBOX_DOCKERFILE = Path(__file__).resolve().parents[1] / "docker" / "sandbox.Dockerfile"


def docker_available() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_sandbox_image(image: str) -> None:
    """Build the sandbox image from docker/sandbox.Dockerfile if it is not present."""
    found = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    if found.returncode == 0:
        return
    subprocess.run(
        ["docker", "build", "-q", "-t", image, "-f", str(SANDBOX_DOCKERFILE), "."],
        cwd=SANDBOX_DOCKERFILE.parent,
        check=True,
        capture_output=True,
    )


class DockerPytestRunner:
    """Runs pytest inside a locked-down, throwaway container.

    Sandbox: non-root user, no network, read-only filesystem (workspace mounted
    read-only, small writable /tmp), memory/CPU/process limits, all Linux
    capabilities dropped, no host environment variables, no Docker socket, and a
    wall-clock timeout after which the container is killed.
    """

    def __init__(
        self,
        image: str = "swe-agent-sandbox:latest",
        timeout_s: int = 120,
        memory: str = "512m",
        cpus: float = 1.0,
        network: bool = False,
    ) -> None:
        self.image, self.timeout_s = image, timeout_s
        self.memory, self.cpus, self.network = memory, cpus, network

    def command(self, workspace: Path, name: str) -> list[str]:
        return [
            "docker", "run", "--rm", "--name", name,
            "--network", "bridge" if self.network else "none",
            "--user", "10001:10001",
            "--memory", self.memory, "--memory-swap", self.memory,
            "--cpus", str(self.cpus),
            "--pids-limit", "256",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-e", "HOME=/tmp",
            "-v", f"{workspace.resolve()}:/work:ro",
            "-w", "/work",
            self.image,
            "python", "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider",
        ]  # fmt: skip

    def run(self, workspace: Path) -> TestRun:
        ensure_sandbox_image(self.image)
        name = f"swe-sandbox-{uuid.uuid4().hex[:12]}"
        start = time.monotonic()
        try:
            proc = subprocess.run(
                self.command(workspace, name),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "kill", name], capture_output=True)
            out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            run = parse_pytest_output(out, 124, time.monotonic() - start)
            run.timed_out = True
            return run
        return parse_pytest_output(
            proc.stdout + proc.stderr, proc.returncode, time.monotonic() - start
        )
