import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from swe_agent.code_index import index_repo
from swe_agent.retrieval import Retriever, default_embedder, tokenize

BUGGY_APP = Path(__file__).resolve().parents[1] / "examples" / "buggy_app"
ISSUE = "Login crashes when email is missing"


class HashingEmbedder:
    """Deterministic bag-of-words embedder for tests (no model download)."""

    def encode(self, texts):
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for row, text in enumerate(texts):
            for tok in tokenize(text):
                out[row, int(hashlib.md5(tok.encode()).hexdigest(), 16) % 64] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


def test_tokenize_splits_identifiers():
    assert tokenize("normalizeEmail(data['email'])") == ["normalize", "email", "data", "email"]
    assert tokenize("Login crashes") == ["login", "crash"]


def test_keyword_search_ranks_login_first():
    hits = Retriever(index_repo(BUGGY_APP)).search(ISSUE, k=3, use_embeddings=False)
    assert hits[0].symbol.qualname == "login"
    assert all(not h.symbol.is_test for h in hits)


def test_hybrid_search_uses_embedder():
    retriever = Retriever(index_repo(BUGGY_APP), embedder=HashingEmbedder())
    hits = retriever.search(ISSUE, k=3)
    assert "login" in [h.symbol.qualname for h in hits]
    assert any(h.embedding_score > 0 for h in hits)


def test_include_tests_flag():
    retriever = Retriever(index_repo(BUGGY_APP), include_tests=True)
    names = [h.symbol.qualname for h in retriever.search(ISSUE, k=10, use_embeddings=False)]
    assert "test_login_missing_email" in names


HAS_ST = importlib.util.find_spec("sentence_transformers") is not None


@pytest.mark.skipif(not HAS_ST, reason="sentence-transformers not installed")
def test_real_sentence_embeddings_find_login():
    retriever = Retriever(index_repo(BUGGY_APP), embedder=default_embedder())
    hits = retriever.search(ISSUE, k=3)
    assert "login" in [h.symbol.qualname for h in hits]
