"""Code retrieval: BM25 keyword search plus optional sentence-embedding search.

No vector database: embeddings for a repo's symbols are kept in a numpy array.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from swe_agent.code_index import Symbol

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

STOPWORDS = set(
    """a an and are as at be but by for from has have if in into is it its of on or that the
    this to was were when where which while with not no self def return none true false
    import class pass str int dict list bool""".split()
)


def tokenize(text: str) -> list[str]:
    """Split text and identifiers (snake_case, camelCase) into lowercase word tokens."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    tokens = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9]*", text):
        word = word.lower()
        if len(word) < 2 or word in STOPWORDS:
            continue
        # Very light stemming so "crashes"/"crash", "emails"/"email" match.
        for suffix in ("es", "s"):
            if word.endswith(suffix) and len(word) > len(suffix) + 3:
                word = word[: -len(suffix)]
                break
        tokens.append(word)
    return tokens


def symbol_document(symbol: Symbol) -> list[str]:
    """Tokens that describe a symbol. Names count three times, so they matter more."""
    name_tokens = tokenize(symbol.qualname) + tokenize(symbol.path)
    return name_tokens * 3 + tokenize(symbol.docstring) + tokenize(symbol.source)


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tfs = [Counter(d) for d in docs]
        self.lengths = [len(d) for d in docs]
        self.avg_len = (sum(self.lengths) / len(docs)) if docs else 0.0
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tfs))
        for i, tf in enumerate(self.tfs):
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / (self.avg_len or 1))
            for term in set(query):
                if term in tf:
                    out[i] += self.idf[term] * tf[term] * (self.k1 + 1) / (tf[term] + norm)
        return out


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalized vector per text, shape (len(texts), dim)."""
        ...


class SentenceTransformerEmbedder:
    """Wraps a sentence-transformers (PyTorch) model. Loaded on first use."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device="cpu")
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)


def default_embedder() -> Embedder | None:
    """The sentence-transformers embedder if installed, otherwise None (keyword-only)."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return None
    return SentenceTransformerEmbedder()


@dataclass
class Hit:
    symbol: Symbol
    score: float
    keyword_score: float
    embedding_score: float


def _minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0 or float(x.max() - x.min()) == 0.0:
        return np.zeros_like(x)
    return (x - x.min()) / (x.max() - x.min())


class Retriever:
    """Ranks a repo's symbols against a natural-language query."""

    def __init__(
        self,
        symbols: list[Symbol],
        embedder: Embedder | None = None,
        include_tests: bool = False,
        embedding_weight: float = 0.5,
    ) -> None:
        self.symbols = [s for s in symbols if include_tests or not s.is_test]
        self.embedder = embedder
        self.embedding_weight = embedding_weight
        self.bm25 = BM25([symbol_document(s) for s in self.symbols])
        self._vectors: np.ndarray | None = None

    def _symbol_vectors(self) -> np.ndarray:
        if self._vectors is None:
            texts = [f"{s.path} {s.qualname}\n{s.source[:2000]}" for s in self.symbols]
            self._vectors = self.embedder.encode(texts)
        return self._vectors

    def search(self, query: str, k: int = 5, use_embeddings: bool = True) -> list[Hit]:
        if not self.symbols:
            return []
        kw = self.bm25.scores(tokenize(query))
        emb = np.zeros(len(self.symbols))
        use_emb = use_embeddings and self.embedder is not None
        if use_emb:
            query_vec = self.embedder.encode([query])[0]
            emb = self._symbol_vectors() @ query_vec
            w = self.embedding_weight
            combined = (1 - w) * _minmax(kw) + w * _minmax(emb)
        else:
            combined = _minmax(kw)
        order = np.argsort(-combined, kind="stable")[:k]
        return [
            Hit(self.symbols[i], float(combined[i]), float(kw[i]), float(emb[i])) for i in order
        ]
