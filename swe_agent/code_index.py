"""Python AST indexing: find every function, method and class in a repo."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", ".tox"}


@dataclass(frozen=True)
class Symbol:
    """A function, method or class found in the code."""

    kind: str  # "function" | "method" | "class"
    name: str
    qualname: str  # e.g. "UserStore.add"
    path: str  # relative to repo root, POSIX style
    start_line: int
    end_line: int
    source: str
    docstring: str
    is_test: bool

    @property
    def location(self) -> str:
        return f"{self.path}:{self.start_line}-{self.end_line}"


def _is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    return any(p in ("tests", "test") for p in parts[:-1]) or parts[-1].startswith("test_")


def iter_python_files(repo: Path) -> list[Path]:
    files = []
    for path in sorted(repo.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.relative_to(repo).parts):
            continue
        files.append(path)
    return files


def index_file(repo: Path, path: Path) -> list[Symbol]:
    """Parse one file and return its symbols. Files that don't parse are skipped."""
    rel = path.relative_to(repo).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError:
        return []
    lines = text.splitlines()
    is_test = _is_test_path(rel)
    symbols: list[Symbol] = []

    def visit(node: ast.AST, prefix: str, in_class: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                is_class = isinstance(child, ast.ClassDef)
                kind = "class" if is_class else ("method" if in_class else "function")
                qualname = f"{prefix}{child.name}"
                # Include decorators in the snippet.
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                end = child.end_lineno or child.lineno
                symbols.append(
                    Symbol(
                        kind=kind,
                        name=child.name,
                        qualname=qualname,
                        path=rel,
                        start_line=start,
                        end_line=end,
                        source="\n".join(lines[start - 1 : end]),
                        docstring=ast.get_docstring(child) or "",
                        is_test=is_test,
                    )
                )
                visit(child, f"{qualname}.", in_class=is_class)

    visit(tree, "", in_class=False)
    return symbols


def index_repo(repo: Path | str) -> list[Symbol]:
    """Return all symbols in all Python files under `repo`."""
    repo = Path(repo).resolve()
    symbols: list[Symbol] = []
    for path in iter_python_files(repo):
        symbols.extend(index_file(repo, path))
    return symbols
