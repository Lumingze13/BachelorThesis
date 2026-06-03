"""
Pluggable text embedder for SSR (Semantic Similarity Rating).

Default offline embedder: char n-gram TF-IDF-style hashing vectorizer.
Deterministic, no network, no model download.

To swap in sentence-transformers for real use:
    from eval_pipeline.embedder import SentenceTransformerEmbedder
    embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
"""

import hashlib
import re
from typing import List
import numpy as np


class BaseEmbedder:
    """Abstract base class for embedders."""

    def embed(self, text: str) -> np.ndarray:
        raise NotImplementedError

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return np.stack([self.embed(t) for t in texts])

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))


class HashingEmbedder(BaseEmbedder):
    """
    Deterministic offline char n-gram hashing embedder.

    Splits text into character n-grams (n=3,4), hashes each with SHA-256,
    and accumulates a sparse-dense 512-dim vector. No network, no deps beyond numpy.
    Suitable as a stub for pipeline testing.

    For real use, replace with SentenceTransformerEmbedder.
    """

    def __init__(self, dim: int = 512, ngram_sizes: tuple = (3, 4)):
        self.dim = dim
        self.ngram_sizes = ngram_sizes

    def _extract_ngrams(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"\s+", " ", text).strip()
        ngrams = []
        for n in self.ngram_sizes:
            for i in range(len(text) - n + 1):
                ngrams.append(text[i: i + n])
        return ngrams

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        ngrams = self._extract_ngrams(text)
        if not ngrams:
            return vec
        for ng in ngrams:
            h = int(hashlib.sha256(ng.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            # sign from a second hash
            sign = 1 if (h >> 256 - 1) & 1 == 0 else -1
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Real sentence-transformer embedder.
    Only usable when sentence-transformers is installed and a model is available.
    NOT called during offline demo/tests.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(model_name)
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            )

    def embed(self, text: str) -> np.ndarray:
        return self._model.encode(text, normalize_embeddings=True)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True)


def get_default_embedder() -> BaseEmbedder:
    """Return the default offline embedder."""
    return HashingEmbedder()
