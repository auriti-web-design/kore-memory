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

from . import config

MODEL_NAME = config.EMBED_MODEL
MAX_EMBED_CHARS = config.MAX_EMBED_CHARS


@lru_cache(maxsize=1)
def get_model() -> "SentenceTransformer":
    """Carica il modello una volta e lo tiene in cache."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def _truncate(text: str, max_chars: int = MAX_EMBED_CHARS) -> str:
    """Tronca il testo al limite massimo per evitare OOM."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def embed(text: str) -> list[float]:
    """Restituisce il vettore embedding per un singolo testo."""
    model = get_model()
    vector = model.encode(_truncate(text), normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Restituisce i vettori embedding per una lista di testi."""
    model = get_model()
    truncated = [_truncate(t) for t in texts]
    vectors = model.encode(truncated, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product of two normalized vectors = cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


def serialize(vector: list[float]) -> str:
    return json.dumps(vector)


def deserialize(blob: str) -> list[float]:
    return json.loads(blob)
