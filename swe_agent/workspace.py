"""Make an isolated copy of a repo so the original is never modified."""

from __future__ import annotations

import shutil
from pathlib import Path

IGNORE = shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", ".pytest_cache", "*.pyc")


def make_workspace(repo: Path | str, dest: Path | str) -> Path:
    repo, dest = Path(repo).resolve(), Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(repo, dest, ignore=IGNORE)
    return dest
