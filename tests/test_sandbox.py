"""Docker sandbox tests. Skipped when Docker is not running."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from swe_agent.test_runner import DockerPytestRunner, docker_available

pytestmark = pytest.mark.skipif(not docker_available(), reason="Docker is not running")

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"

SANDBOX_CHECKS = """
import os
import socket

import pytest


def test_runs_as_non_root():
    assert os.getuid() != 0


def test_no_network():
    with pytest.raises(OSError):
        socket.create_connection(("1.1.1.1", 53), timeout=3)


def test_no_host_credentials():
    assert "ANTHROPIC_API_KEY" not in os.environ
    # GPG_KEY is baked into the official python image (public key id, not a secret).
    names = [k for k in os.environ if k != "GPG_KEY"]
    assert [k for k in names if "KEY" in k or "TOKEN" in k or "SECRET" in k] == []


def test_no_docker_socket():
    assert not os.path.exists("/var/run/docker.sock")


def test_workspace_is_read_only():
    with pytest.raises(OSError):
        open("/work/written_by_test.txt", "w")


def test_memory_limit_applied():
    with open("/sys/fs/cgroup/memory.max") as f:
        assert int(f.read()) == 512 * 1024 * 1024
"""


def write_repo(root: Path, test_source: str) -> Path:
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_checks.py").write_text(textwrap.dedent(test_source))
    return root


def test_sandbox_restrictions(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "host-secret-should-not-leak")
    run = DockerPytestRunner().run(write_repo(tmp_path / "repo", SANDBOX_CHECKS))
    assert run.ok, run.output
    assert run.passed == 6
    assert not (tmp_path / "repo" / "written_by_test.txt").exists()


def test_timeout_kills_container(tmp_path):
    repo = write_repo(tmp_path / "repo", "import time\n\ndef test_slow():\n    time.sleep(60)\n")
    run = DockerPytestRunner(timeout_s=5).run(repo)
    assert run.timed_out and not run.ok
    names = subprocess.run(
        ["docker", "ps", "--filter", "name=swe-sandbox-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    ).stdout
    assert names.strip() == ""


def test_buggy_app_fails_then_reference_fix_passes(tmp_path):
    runner = DockerPytestRunner()
    before = runner.run(BUGGY_APP)
    assert (before.passed, before.failed) == (6, 2)

    repo = tmp_path / "buggy_app"
    shutil.copytree(BUGGY_APP, repo)
    auth = repo / "app" / "auth.py"
    auth.write_text(
        auth.read_text().replace(
            'email = normalize_email(data["email"])',
            'email = data.get("email")\n    if not email:\n'
            '        return LoginResult(ok=False, error="email is required")\n'
            "    email = normalize_email(email)",
        )
    )
    after = runner.run(repo)
    assert after.ok and after.passed == 8
