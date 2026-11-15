"""Run the multi-agent system on one repo + issue and return a final report."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from swe_agent.agents import Localizer, Patcher, Planner, Verifier
from swe_agent.config import Settings, load_settings
from swe_agent.graph import build_graph
from swe_agent.llm import LLM, AnthropicLLM
from swe_agent.retrieval import Embedder, default_embedder
from swe_agent.test_runner import DockerPytestRunner, LocalPytestRunner, TestRunner
from swe_agent.workspace import make_workspace

DEFAULT_WORKSPACE_ROOT = Path(".workspaces")


@dataclass
class RunOptions:
    planning_depth: str = "full"  # "full" | "reduced"
    use_embeddings: bool = True
    feedback_mode: str = "full"  # "full" | "minimal"
    max_retries: int | None = None  # None -> settings.max_patch_retries
    top_k: int = 5
    sandbox: str = "docker"  # "docker" | "local"


@dataclass
class RunResult:
    issue: str
    repo: str
    status: str
    attempts: int
    duration_s: float
    plan: dict[str, Any] = field(default_factory=dict)
    relevant_files: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    diff: str = ""
    test_result: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    workspace: str = ""
    mode: str = "multi_agent"
    llm_usage: dict[str, int] = field(default_factory=dict)

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"


def new_workspace(repo: Path | str, workspace_root: Path | str) -> Path:
    run_dir = Path(workspace_root) / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    return make_workspace(repo, run_dir / "repo")


def llm_usage(llm: LLM) -> dict[str, int]:
    usage = getattr(llm, "usage", None)
    return asdict(usage) if is_dataclass(usage) else {}


def make_runner(settings: Settings, sandbox: str) -> TestRunner:
    if sandbox == "local":
        return LocalPytestRunner(timeout_s=settings.sandbox_timeout_seconds)
    return DockerPytestRunner(
        image=settings.sandbox_image,
        timeout_s=settings.sandbox_timeout_seconds,
        memory=settings.sandbox_memory,
        cpus=settings.sandbox_cpus,
    )


def run_agent(
    repo: Path | str,
    issue: str,
    *,
    settings: Settings | None = None,
    llm: LLM | None = None,
    runner: TestRunner | None = None,
    embedder: Embedder | None = None,
    options: RunOptions | None = None,
    workspace_root: Path | str = DEFAULT_WORKSPACE_ROOT,
    test_targets: list[str] | None = None,
) -> RunResult:
    settings = settings or load_settings()
    options = options or RunOptions()
    llm = llm or AnthropicLLM(settings)
    runner = runner or make_runner(settings, options.sandbox)
    if options.use_embeddings and embedder is None:
        embedder = default_embedder()
    max_retries = settings.max_patch_retries if options.max_retries is None else options.max_retries

    start = time.monotonic()
    workspace = new_workspace(repo, workspace_root)

    graph = build_graph(
        Planner(llm, depth=options.planning_depth),
        Localizer(embedder=embedder, k=options.top_k, use_embeddings=options.use_embeddings),
        Patcher(llm),
        Verifier(runner, feedback_mode=options.feedback_mode),
        max_retries=max_retries,
    )
    final = graph.invoke(
        {
            "issue": issue,
            "repo_path": str(Path(repo).resolve()),
            "workspace_path": str(workspace.resolve()),
            "attempts": 0,
            "test_targets": test_targets,
            "log": [],
        },
        {"recursion_limit": 50},
    )
    return RunResult(
        issue=issue,
        repo=str(Path(repo).resolve()),
        status=final["status"],
        attempts=final.get("attempts", 0),
        duration_s=round(time.monotonic() - start, 3),
        plan=final.get("plan", {}),
        relevant_files=final.get("relevant_files", []),
        candidates=final.get("candidates", []),
        diff=final.get("diff", ""),
        test_result=final.get("test_result", {}),
        log=final.get("log", []),
        workspace=str(workspace),
        llm_usage=llm_usage(llm),
    )
