import json

import pytest

from swe_agent.agents import Localizer, Patcher, Planner, Verifier
from swe_agent.agents.patcher import PatchError, apply_edits
from swe_agent.demo import BAD_PATCH, GOOD_PATCH, PLAN_REPLY  # noqa: F401 (re-exported)
from swe_agent.demo import DEMO_ISSUE as ISSUE
from swe_agent.demo import DEMO_REPO as BUGGY_APP
from swe_agent.llm import FakeLLM
from swe_agent.test_runner import LocalPytestRunner
from swe_agent.workspace import make_workspace


@pytest.fixture
def workspace(tmp_path):
    return make_workspace(BUGGY_APP, tmp_path / "ws")


def base_state(workspace):
    return {"issue": ISSUE, "repo_path": str(BUGGY_APP), "workspace_path": str(workspace)}


def test_planner_full_uses_llm_and_lists_files(workspace):
    llm = FakeLLM([PLAN_REPLY])
    out = Planner(llm)(base_state(workspace))
    assert out["plan"]["suspect_symbols"] == ["login"]
    assert "app/auth.py" in llm.calls[0][1]  # file list was sent to the model
    assert out["status"] == "planned"


def test_planner_reduced_needs_no_llm(workspace):
    out = Planner(None, depth="reduced")(base_state(workspace))
    assert out["plan"]["search_terms"] == ["login", "crash", "email", "missing"]


def test_localizer_finds_login(workspace):
    state = base_state(workspace) | Planner(FakeLLM([PLAN_REPLY]))(base_state(workspace))
    out = Localizer(k=3)(state)
    assert out["candidates"][0]["qualname"] == "login"
    assert out["relevant_files"][0] == "app/auth.py"
    assert 'data["email"]' in out["candidates"][0]["source"]


def test_apply_edits_rejects_bad_edits(workspace):
    with pytest.raises(PatchError, match="0 times"):
        apply_edits(workspace, [{"path": "app/auth.py", "search": "nope", "replace": "x"}], {})
    with pytest.raises(PatchError, match="bad path"):
        apply_edits(workspace, [{"path": "../outside.py", "search": "a", "replace": "b"}], {})


def test_full_chain_with_retry(workspace):
    """planner -> localizer -> patcher -> verifier, with a bad first patch and a retry."""
    llm = FakeLLM([PLAN_REPLY, BAD_PATCH, GOOD_PATCH])
    planner, localizer, patcher = Planner(llm), Localizer(k=3), Patcher(llm)
    verifier = Verifier(LocalPytestRunner())

    state = base_state(workspace)
    for agent in (planner, localizer, patcher, verifier):
        state |= agent(state)
    assert state["status"] == "failed"
    assert state["attempts"] == 1
    assert "test_login_none_email" in state["feedback"]  # concrete feedback for the retry

    state |= patcher(state)
    # Retry prompt includes the verifier's feedback and the previous diff.
    assert "test_login_none_email" in llm.calls[-1][1]
    assert state["diff"].startswith("--- a/app/auth.py")
    assert 'data.get("email", "")' not in (workspace / "app/auth.py").read_text()  # reset first
    state |= verifier(state)
    assert state["status"] == "resolved"
    assert state["attempts"] == 2
    assert state["test_result"]["passed"] == 8
    # The original repo is untouched.
    assert 'data["email"]' in (BUGGY_APP / "app/auth.py").read_text()


def test_unappliable_patch_is_reported(workspace):
    llm = FakeLLM([json.dumps({"edits": [{"path": "app/auth.py", "search": "zzz"}]})])
    state = base_state(workspace) | {"candidates": []}
    state |= Patcher(llm)(state)
    assert state["status"] == "patch_failed"
    state |= Verifier(LocalPytestRunner())(state)
    assert state["status"] == "failed"
    assert "could not be applied" in state["feedback"]


def test_minimal_feedback_mode(workspace):
    state = base_state(workspace) | {"patch_error": None}
    out = Verifier(LocalPytestRunner(), feedback_mode="minimal")(state)
    assert out["feedback"] == "The tests still fail."
