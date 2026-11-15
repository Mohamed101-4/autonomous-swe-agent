"""Every eval bug must be real (visible tests fail) and fixable (reference fix passes all)."""

import shutil

import pytest

from swe_agent.agents.patcher import apply_edits
from swe_agent.evaluation import grade, load_bugs
from swe_agent.test_runner import LocalPytestRunner

BUGS = load_bugs()


def test_bug_set_size():
    assert len(BUGS) == 10
    assert len({b.id for b in BUGS}) == 10


@pytest.mark.parametrize("bug", BUGS, ids=lambda b: b.id)
def test_bug_reproduces_and_reference_fix_passes(bug, tmp_path):
    runner = LocalPytestRunner()
    before = runner.run(bug.repo)
    assert before.failed >= 1, before.output
    assert grade(bug.repo, bug, runner).failed >= 1

    repo = tmp_path / "repo"
    shutil.copytree(bug.repo, repo)
    apply_edits(repo, bug.reference_edits, {})
    after = grade(repo, bug, runner)
    assert after.ok, after.output
    assert not any(bug.hidden_tests.name in p.parts for p in repo.rglob("*"))  # repo untouched


def test_hidden_tests_not_in_agent_repo():
    for bug in BUGS:
        names = {p.name for p in bug.repo.rglob("test_*.py")}
        hidden = {p.name for p in bug.hidden_tests.glob("test_*.py")}
        assert hidden and not (names & hidden)


def test_unknown_id_rejected():
    with pytest.raises(ValueError, match="unknown bug ids"):
        load_bugs(ids=["nope"])
