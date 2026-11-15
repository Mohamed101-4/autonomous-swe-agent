from pathlib import Path

from swe_agent.baseline import run_baseline, select_files
from swe_agent.config import load_settings
from swe_agent.llm import FakeLLM
from swe_agent.test_runner import LocalPytestRunner

from .test_agents import BAD_PATCH, GOOD_PATCH, ISSUE

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"


def test_select_files_skips_tests_and_respects_budget():
    files = select_files(BUGGY_APP, ISSUE, max_chars=100_000)
    paths = [f["path"] for f in files]
    assert paths[0] == "app/auth.py"
    assert not any(p.startswith("tests/") for p in paths)
    small = select_files(BUGGY_APP, ISSUE, max_chars=1500)
    assert sum(len(f["source"]) for f in small) <= 1500


def run(tmp_path, reply):
    return run_baseline(
        BUGGY_APP, ISSUE, settings=load_settings(env={}), llm=FakeLLM([reply]),
        runner=LocalPytestRunner(), workspace_root=tmp_path,
    )  # fmt: skip


def test_baseline_single_call_resolves(tmp_path):
    result = run(tmp_path, GOOD_PATCH)
    assert result.mode == "baseline" and result.resolved and result.attempts == 1


def test_baseline_has_no_retry(tmp_path):
    result = run(tmp_path, BAD_PATCH)  # FakeLLM would fail if asked twice
    assert result.status == "failed" and result.attempts == 1
