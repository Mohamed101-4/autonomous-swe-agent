"""Command-line entry point.

Example:
    python main.py --repo ./examples/buggy_app --issue "Login crashes when email is missing"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swe_agent.config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find and fix a bug in a Python repo.")
    parser.add_argument("--repo", required=True, type=Path, help="Path to the target repo")
    parser.add_argument("--issue", required=True, help="Bug description in plain English")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo.is_dir():
        print(f"error: repo path does not exist: {args.repo}", file=sys.stderr)
        return 2

    settings = load_settings()
    print(f"Repo:  {args.repo.resolve()}")
    print(f"Issue: {args.issue}")
    print(f"Model: {settings.model} (API key configured: {settings.has_llm_key})")
    print("The agent pipeline is not implemented yet (coming in Phases 2-4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
