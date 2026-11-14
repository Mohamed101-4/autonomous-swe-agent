from swe_agent.test_runner import parse_pytest_output


def test_parse_failures():
    out = (
        "..F\nFAILED tests/test_a.py::test_x - KeyError\n"
        "ERROR tests/test_b.py::test_y\n1 failed, 2 passed, 1 error in 0.1s\n"
    )
    run = parse_pytest_output(out, 1, 0.1)
    assert (run.passed, run.failed, run.errors) == (2, 1, 1)
    assert run.failing_tests == ["tests/test_a.py::test_x", "tests/test_b.py::test_y"]
    assert not run.ok


def test_parse_success_and_no_tests():
    assert parse_pytest_output("3 passed in 0.01s", 0, 0.01).ok
    assert not parse_pytest_output("no tests ran in 0.01s", 5, 0.01).ok
