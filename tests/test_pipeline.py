from pathlib import Path

import pytest

from swe_agent.config import load_settings
from swe_agent.llm import FakeLLM
from swe_agent.pipeline import RunOptions, run_agent
from swe_agent.test_runner import DockerPytestRunner, LocalPytestRunner, docker_available

from .test_agents import BAD_PATCH, GOOD_PATCH, ISSUE, PLAN_REPLY

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"
SETTINGS = load_settings(env={})  # no API key needed: the LLM is scripted


def run(tmp_path, replies, runner=None, **opts):
    return run_agent(
        BUGGY_APP,
        ISSUE,
        settings=SETTINGS,
        llm=FakeLLM(list(replies)),
        runner=runner or LocalPytestRunner(),
        options=RunOptions(use_embeddings=False, **opts),
        workspace_root=tmp_path,
    )


def agent_order(log):
    order = [line.split(":")[0] for line in log]
    return [a for i, a in enumerate(order) if i == 0 or a != order[i - 1]]


def test_agents_run_in_order_and_resolve_first_try(tmp_path):
    result = run(tmp_path, [PLAN_REPLY, GOOD_PATCH])
    assert result.resolved
    assert result.attempts == 1
    assert agent_order(result.log) == ["planner", "localizer", "patcher", "verifier", "report"]
    assert result.relevant_files[0] == "app/auth.py"
    assert "+    if not email:" in result.diff
    assert result.test_result["passed"] == 8


def test_retry_after_failed_patch(tmp_path):
    result = run(tmp_path, [PLAN_REPLY, BAD_PATCH, GOOD_PATCH])
    assert result.resolved
    assert result.attempts == 2
    assert agent_order(result.log) == [
        "planner", "localizer", "patcher", "verifier", "patcher", "verifier", "report",
    ]  # fmt: skip


def test_gives_up_after_max_retries(tmp_path):
    result = run(tmp_path, [PLAN_REPLY, BAD_PATCH, BAD_PATCH, BAD_PATCH])
    assert result.status == "failed"
    assert result.attempts == 3  # 1 try + 2 retries
    assert result.log[-1] == "report: failed after 3 patch attempt(s)"


def test_max_retries_option(tmp_path):
    result = run(tmp_path, [PLAN_REPLY, BAD_PATCH], max_retries=0)
    assert result.status == "failed" and result.attempts == 1


@pytest.mark.skipif(not docker_available(), reason="Docker is not running")
def test_end_to_end_in_docker_sandbox(tmp_path):
    result = run(tmp_path, [PLAN_REPLY, BAD_PATCH, GOOD_PATCH], runner=DockerPytestRunner())
    assert result.resolved and result.attempts == 2
    assert 'data["email"]' in (BUGGY_APP / "app/auth.py").read_text()  # original untouched
