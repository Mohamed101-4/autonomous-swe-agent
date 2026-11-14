from pathlib import Path

from swe_agent.code_index import index_file, index_repo

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"


def test_index_finds_functions_classes_and_methods():
    symbols = {s.qualname: s for s in index_repo(BUGGY_APP)}
    assert symbols["login"].kind == "function"
    assert symbols["login"].path == "app/auth.py"
    assert symbols["UserStore"].kind == "class"
    assert symbols["UserStore.add"].kind == "method"
    assert symbols["LoginResult"].kind == "class"


def test_symbol_source_and_lines_match_file():
    login = next(s for s in index_repo(BUGGY_APP) if s.qualname == "login")
    lines = (BUGGY_APP / login.path).read_text().splitlines()
    assert login.source.splitlines()[0] == lines[login.start_line - 1]
    assert 'data["email"]' in login.source
    assert not login.is_test


def test_test_files_are_flagged():
    tests = [s for s in index_repo(BUGGY_APP) if s.name == "test_login_missing_email"]
    assert tests and tests[0].is_test


def test_decorators_and_syntax_errors(tmp_path):
    (tmp_path / "mod.py").write_text("import functools\n\n@functools.cache\ndef f():\n    return 1\n")
    (tmp_path / "broken.py").write_text("def oops(:\n")
    (f,) = index_file(tmp_path, tmp_path / "mod.py")
    assert f.start_line == 3 and f.source.startswith("@functools.cache")
    assert index_file(tmp_path, tmp_path / "broken.py") == []
