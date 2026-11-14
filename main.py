"""Command-line entry point.

Example:
    python main.py --repo ./examples/buggy_app --issue "Login crashes when email is missing"
    python main.py --history 10
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from swe_agent.config import load_settings
from swe_agent.pipeline import RunOptions, RunResult, run_agent
from swe_agent.test_runner import docker_available


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Find and fix a bug in a Python repo.")
    p.add_argument("--repo", type=Path, help="path to the target repo")
    p.add_argument("--issue", help="bug description in plain English")
    p.add_argument(
        "--sandbox",
        choices=["docker", "local"],
        default="docker",
        help="where to run tests (default: docker; 'local' is NOT isolated)",
    )
    p.add_argument(
        "--planning",
        choices=["full", "reduced"],
        default="full",
        help="'reduced' skips the LLM planner and uses issue keywords",
    )
    p.add_argument(
        "--no-embeddings",
        action="store_true",
        help="keyword search only (no sentence-embedding retrieval)",
    )
    p.add_argument(
        "--feedback",
        choices=["full", "minimal"],
        default="full",
        help="verifier feedback given to the patcher on retries",
    )
    p.add_argument("--max-retries", type=int, help="retries after a failed patch (default 2)")
    p.add_argument("--top-k", type=int, default=5, help="code snippets given to the patcher")
    p.add_argument("--repo-id", help="name stored in the database (default: folder name)")
    p.add_argument("--no-db", action="store_true", help="do not record the run in Postgres")
    p.add_argument("--history", type=int, metavar="N", help="show the last N recorded runs")
    return p  # fmt: skip


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def print_report(result: RunResult) -> None:
    section("Investigation steps")
    for line in result.log:
        print(f"  {line}")

    section("Relevant files")
    for c in result.candidates:
        print(f"  {c['path']}:{c['start_line']}-{c['end_line']}  {c['qualname']}  ({c['score']})")

    section("Proposed patch")
    print(result.diff.rstrip() if result.diff else "  (no patch applied)")

    section("Test results")
    t = result.test_result
    if t:
        print(f"  {t['passed']} passed, {t['failed']} failed, {t['errors']} errors "
              f"in {t['duration_s']:.2f}s")  # fmt: skip
        for name in t.get("failing_tests", []):
            print(f"  FAILED {name}")
    else:
        print("  (tests not run)")

    section("Outcome")
    print(f"  {result.status.upper()} after {result.attempts} patch attempt(s) "
          f"in {result.duration_s:.1f}s")  # fmt: skip
    print(f"  Patched copy: {result.workspace}")


def record(url: str | None, result: RunResult, repo_id: str | None, options: RunOptions) -> None:
    if not url:
        print("\n(DATABASE_URL not set; run not recorded)")
        return
    import psycopg

    from swe_agent.db import init_db, record_run

    try:
        init_db(url)
        run_id = record_run(url, result, repo_id=repo_id, options=dataclasses.asdict(options))
    except psycopg.Error as exc:
        print(f"\nwarning: could not record run in Postgres: {exc}".rstrip(), file=sys.stderr)
        return
    print(f"\nRun recorded in Postgres (id={run_id})")


def show_history(url: str | None, limit: int) -> int:
    if not url:
        print("error: DATABASE_URL is not set", file=sys.stderr)
        return 2
    from swe_agent.db import init_db, list_runs

    init_db(url)
    for r in list_runs(url, limit):
        if r["tests_passed"] is None:
            tests = "-"
        else:
            tests = f"{r['tests_passed']}/{r['tests_passed'] + (r['tests_failed'] or 0)}"
        print(f"#{r['id']:<4} {r['created_at'].astimezone():%Y-%m-%d %H:%M}  {r['repo_id']:<16} "
              f"{r['status']:<9} attempts={r['attempts']} tests={tests:<6} "
              f"{r['execution_time_s'] or 0:6.1f}s  {r['bug_description'][:50]}")  # fmt: skip
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.history is not None:
        return show_history(settings.database_url, args.history)
    if not args.repo or not args.issue:
        parser.error("--repo and --issue are required")
    if not args.repo.is_dir():
        print(f"error: repo path does not exist: {args.repo}", file=sys.stderr)
        return 2
    if not settings.has_llm_key:
        print("error: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
              file=sys.stderr)  # fmt: skip
        return 2
    if args.sandbox == "docker" and not docker_available():
        print("error: Docker is not running. Start Docker, or use --sandbox local "
              "(runs tests on this machine without isolation).", file=sys.stderr)  # fmt: skip
        return 2

    options = RunOptions(
        planning_depth=args.planning,
        use_embeddings=not args.no_embeddings,
        feedback_mode=args.feedback,
        max_retries=args.max_retries,
        top_k=args.top_k,
        sandbox=args.sandbox,
    )
    print(f"Repo:  {args.repo.resolve()}")
    print(f"Issue: {args.issue}")
    print(f"Model: {settings.model} | sandbox: {args.sandbox} | planning: {args.planning} | "
          f"embeddings: {options.use_embeddings} | feedback: {args.feedback}")  # fmt: skip
    print("Running agents...")

    try:
        result = run_agent(args.repo, args.issue, settings=settings, options=options)
    except Exception as exc:  # report and record any crash instead of a bare traceback
        print(f"error: the run crashed: {type(exc).__name__}: {exc}", file=sys.stderr)
        result = RunResult(
            issue=args.issue, repo=str(args.repo.resolve()), status="error", attempts=0,
            duration_s=0.0, log=[f"error: {type(exc).__name__}: {exc}"],
        )  # fmt: skip
        if not args.no_db:
            record(settings.database_url, result, args.repo_id, options)
        return 1
    print_report(result)
    if not args.no_db:
        record(settings.database_url, result, args.repo_id, options)
    return 0 if result.resolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
