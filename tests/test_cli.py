from pathlib import Path

import pytest

import main
from swe_agent.config import load_settings
from swe_agent.llm import FakeLLM
from swe_agent.pipeline import run_agent
from swe_agent.test_runner import LocalPytestRunner

from .test_agents import BAD_PATCH, GOOD_PATCH, ISSUE, PLAN_REPLY
from .test_db import URL as DB_URL
from .test_db import _reachable as db_reachable

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    """Pretend a key is configured, script the LLM, run tests locally, no real DB."""
    env = {"ANTHROPIC_API_KEY": "test-not-a-real-key"}
    monkeypatch.setattr(main, "load_settings", lambda: load_settings(env=env))

    def scripted_run(repo, issue, *, settings, options):
        return run_agent(
            repo, issue, settings=settings, options=options,
            llm=FakeLLM([PLAN_REPLY, BAD_PATCH, GOOD_PATCH]),
            runner=LocalPytestRunner(), embedder=None, workspace_root=tmp_path,
        )  # fmt: skip

    monkeypatch.setattr(main, "run_agent", scripted_run)
    return env


def test_cli_prints_full_report(fake_env, capsys):
    code = main.main(
        ["--repo", str(BUGGY_APP), "--issue", ISSUE, "--sandbox", "local", "--no-embeddings"]
    )
    out = capsys.readouterr().out
    assert code == 0
    for heading in ("Investigation steps", "Relevant files", "Proposed patch", "Test results"):
        assert f"=== {heading} ===" in out
    assert "app/auth.py" in out
    assert "+    if not email:" in out
    assert "8 passed, 0 failed" in out
    assert "RESOLVED after 2 patch attempt(s)" in out
    assert "DATABASE_URL not set" in out


def test_cli_requires_api_key(monkeypatch, capsys):
    monkeypatch.setattr(main, "load_settings", lambda: load_settings(env={}))
    assert main.main(["--repo", str(BUGGY_APP), "--issue", ISSUE]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_cli_rejects_missing_repo(fake_env, tmp_path):
    assert main.main(["--repo", str(tmp_path / "nope"), "--issue", "x"]) == 2


def test_cli_requires_repo_and_issue(fake_env):
    with pytest.raises(SystemExit):
        main.main(["--issue", "x"])


def test_cli_reports_crash(fake_env, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(main, "run_agent", boom)
    code = main.main(["--repo", str(BUGGY_APP), "--issue", ISSUE, "--sandbox", "local"])
    assert code == 1
    assert "model unavailable" in capsys.readouterr().err


@pytest.mark.skipif(not db_reachable(), reason="Postgres not reachable")
def test_cli_records_run_and_shows_history(fake_env, capsys):
    fake_env["DATABASE_URL"] = DB_URL
    args = ["--repo", str(BUGGY_APP), "--issue", ISSUE, "--sandbox", "local", "--no-embeddings"]
    assert main.main([*args, "--repo-id", "cli-test"]) == 0
    out = capsys.readouterr().out
    assert "Run recorded in Postgres (id=" in out

    assert main.main(["--history", "1"]) == 0
    line = capsys.readouterr().out
    assert "cli-test" in line and "resolved" in line and "tests=8/8" in line
