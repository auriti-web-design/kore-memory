"""
Kore — Embedder (v2)
Lazy-loaded sentence embeddings using a small multilingual model.
Model: paraphrase-multilingual-MiniLM-L12-v2 (~120MB, supports Italian + English)
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def get_model() -> "SentenceTransformer":
    """Load model once and cache it in memory."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    """Return embedding vector for a single text."""
    model = get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of texts."""
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product of two normalized vectors = cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


def serialize(vector: list[float]) -> str:
    return json.dumps(vector)


def deserialize(blob: str) -> list[float]:
    return json.loads(blob)
