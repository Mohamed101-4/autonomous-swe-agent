"""Checks that the sample bug is real and reproducible, and that it is fixable."""

import shutil
import subprocess
import sys
from pathlib import Path

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"

BUGGY_LINE = '    email = normalize_email(data["email"])\n'
FIXED_LINES = (
    '    email = data.get("email")\n'
    "    if not email:\n"
    '        return LoginResult(ok=False, error="email is required")\n'
    "    email = normalize_email(email)\n"
)


def run_pytest(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_bug_reproduces():
    result = run_pytest(BUGGY_APP)
    assert result.returncode != 0
    assert "2 failed, 6 passed" in result.stdout
    assert "test_login_missing_email" in result.stdout


def test_reference_fix_makes_tests_pass(tmp_path):
    repo = tmp_path / "buggy_app"
    shutil.copytree(BUGGY_APP, repo)
    auth = repo / "app" / "auth.py"
    source = auth.read_text()
    assert BUGGY_LINE in source
    auth.write_text(source.replace(BUGGY_LINE, FIXED_LINES))

    result = run_pytest(repo)
    assert result.returncode == 0, result.stdout
    assert "8 passed" in result.stdout
