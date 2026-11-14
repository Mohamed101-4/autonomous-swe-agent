"""Postgres tests. Skipped unless a database is reachable.

Uses TEST_DATABASE_URL, else the docker-compose default (docker compose up -d db).
"""

import os

import psycopg
import pytest

from swe_agent.db import init_db, list_runs, record_run
from swe_agent.pipeline import RunResult

URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://swe_agent:swe_agent@localhost:5433/swe_agent"
)


def _reachable() -> bool:
    try:
        psycopg.connect(URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _reachable(), reason="Postgres not reachable")


def make_result(**overrides):
    base = dict(
        issue="Login crashes when email is missing",
        repo="/tmp/somewhere/buggy_app",
        status="resolved",
        attempts=2,
        duration_s=12.5,
        relevant_files=["app/auth.py"],
        diff="--- a/app/auth.py\n+++ b/app/auth.py\n",
        test_result={"passed": 8, "failed": 0, "ok": True, "output": "x" * 10000},
        log=["planner: ...", "report: resolved after 2 patch attempt(s)"],
    )
    return RunResult(**(base | overrides))


def test_init_is_idempotent():
    init_db(URL)
    init_db(URL)


def test_record_and_list_run():
    init_db(URL)
    run_id = record_run(URL, make_result(), options={"planning_depth": "full"})
    with psycopg.connect(URL) as conn:
        row = conn.execute(
            "SELECT repo_id, bug_description, status, attempts, tests_passed, tests_failed,"
            " execution_time_s, test_results, relevant_files, agent_log, options, mode"
            " FROM runs WHERE id = %s",
            (run_id,),
        ).fetchone()
    repo_id, bug, status, attempts, passed, failed, secs, tests, files, log, opts, mode = row
    assert (repo_id, bug, status, attempts) == (
        "buggy_app",
        "Login crashes when email is missing",
        "resolved",
        2,
    )
    assert (passed, failed, secs, mode) == (8, 0, 12.5, "multi_agent")
    assert "output" not in tests and len(tests["output_tail"]) == 4000
    assert files == ["app/auth.py"]
    assert log[-1].startswith("report:")
    assert opts == {"planning_depth": "full"}
    assert list_runs(URL, limit=1)[0]["id"] == run_id


def test_record_failed_run_without_tests():
    init_db(URL)
    run_id = record_run(
        URL, make_result(status="error", attempts=0, test_result={}, diff=""), mode="baseline"
    )
    latest = list_runs(URL, limit=1)[0]
    assert latest["id"] == run_id
    assert latest["status"] == "error" and latest["tests_passed"] is None
