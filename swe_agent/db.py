"""PostgreSQL storage for agent runs (one table, see db/schema.sql)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from swe_agent.pipeline import RunResult

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, connect_timeout=5, row_factory=dict_row)


def init_db(url: str) -> None:
    """Create the schema if it does not exist (safe to call every time)."""
    with connect(url) as conn:
        conn.execute(SCHEMA_PATH.read_text())


def repo_id_for(repo: Path | str) -> str:
    return Path(repo).resolve().name


def record_run(
    url: str,
    result: RunResult,
    *,
    repo_id: str | None = None,
    mode: str = "multi_agent",
    options: dict[str, Any] | None = None,
) -> int:
    """Insert one run and return its id."""
    tests = result.test_result or {}
    with connect(url) as conn:
        row = conn.execute(
            """
            INSERT INTO runs (repo_id, bug_description, mode, status, attempts,
                              tests_passed, tests_failed, test_results, execution_time_s,
                              relevant_files, patch_diff, agent_log, options)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                repo_id or repo_id_for(result.repo),
                result.issue,
                mode,
                result.status,
                result.attempts,
                tests.get("passed"),
                tests.get("failed"),
                Jsonb(_compact_tests(tests)) if tests else None,
                result.duration_s,
                Jsonb(result.relevant_files),
                result.diff or None,
                Jsonb(result.log),
                Jsonb(options or {}),
            ),
        ).fetchone()
    return row["id"]


def _compact_tests(tests: dict[str, Any]) -> dict[str, Any]:
    """Keep counts and failing tests; store only the tail of the raw pytest output."""
    compact = {k: v for k, v in tests.items() if k != "output"}
    compact["output_tail"] = (tests.get("output") or "")[-4000:]
    return compact


def list_runs(url: str, limit: int = 10) -> list[dict[str, Any]]:
    with connect(url) as conn:
        return conn.execute(
            """
            SELECT id, created_at, repo_id, mode, status, attempts, tests_passed,
                   tests_failed, execution_time_s, bug_description
            FROM runs ORDER BY id DESC LIMIT %s
            """,
            (limit,),
        ).fetchall()
