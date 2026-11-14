from pathlib import Path

import main

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"


def test_cli_accepts_repo_and_issue(capsys):
    code = main.main(["--repo", str(BUGGY_APP), "--issue", "Login crashes when email is missing"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Login crashes when email is missing" in out


def test_cli_rejects_missing_repo(tmp_path, capsys):
    code = main.main(["--repo", str(tmp_path / "nope"), "--issue", "x"])
    assert code == 2
