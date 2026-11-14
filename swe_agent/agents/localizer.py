"""Localizer: finds the files and functions most related to the issue."""

from __future__ import annotations

from pathlib import Path

from swe_agent.code_index import index_repo
from swe_agent.retrieval import Embedder, Retriever
from swe_agent.state import AgentState


class Localizer:
    def __init__(
        self, embedder: Embedder | None = None, k: int = 5, use_embeddings: bool = True
    ) -> None:
        self.embedder, self.k, self.use_embeddings = embedder, k, use_embeddings

    def __call__(self, state: AgentState) -> AgentState:
        repo = Path(state.get("workspace_path") or state["repo_path"])
        plan = state.get("plan") or {}
        suspects = set(plan.get("suspect_symbols") or [])
        query = " ".join(
            [state["issue"], plan.get("summary", ""), *plan.get("search_terms", []), *suspects]
        )

        retriever = Retriever(index_repo(repo), embedder=self.embedder)
        hits = retriever.search(query, k=self.k, use_embeddings=self.use_embeddings)

        # Symbols the planner named explicitly go first, even if retrieval missed them.
        named = [s for s in retriever.symbols if s.name in suspects or s.qualname in suspects]
        seen, ordered = set(), []
        for symbol, score in [(s, 1.0) for s in named] + [(h.symbol, h.score) for h in hits]:
            if symbol.location not in seen:
                seen.add(symbol.location)
                ordered.append((symbol, score))
        ordered = ordered[: self.k]

        candidates = [
            {
                "path": s.path,
                "qualname": s.qualname,
                "kind": s.kind,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "score": round(score, 3),
                "source": s.source,
            }
            for s, score in ordered
        ]
        files = list(dict.fromkeys(c["path"] for c in candidates))
        log = list(state.get("log", []))
        mode = "keyword+embedding" if self.use_embeddings and self.embedder else "keyword"
        log.append(f"localizer: searched {len(retriever.symbols)} symbols ({mode})")
        log += [f"localizer:   {c['path']}:{c['start_line']} {c['qualname']}" for c in candidates]
        return {
            "candidates": candidates,
            "relevant_files": files,
            "status": "localized",
            "log": log,
        }
