"""
Kore — Indice vettoriale in-memory
Cache degli embeddings per ricerca semantica veloce.

Strategia:
  - Al primo search, carica tutti gli embeddings dell'agente in memoria
  - Li mantiene in un dict {memory_id: vector} per lookup rapido
  - Invalida la cache quando si aggiungono/eliminano memorie
  - Calcolo batch dot product su vettori normalizzati
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

# --- numpy availability (optional, installed with [semantic]) ---
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False


@dataclass
class _AgentCache:
    """Cache vettoriale per un singolo agente."""
    vectors: dict[int, list[float]] = field(default_factory=dict)
    dirty: bool = True  # forza ricaricamento al primo accesso


class VectorIndex:
    """Indice vettoriale in-memory con invalidazione per agente."""

    def __init__(self) -> None:
        self._caches: dict[str, _AgentCache] = {}
        self._lock = threading.Lock()

    def get_cache(self, agent_id: str) -> _AgentCache:
        with self._lock:
            if agent_id not in self._caches:
                self._caches[agent_id] = _AgentCache()
            return self._caches[agent_id]

    def invalidate(self, agent_id: str) -> None:
        """Invalida la cache per un agente (dopo save/delete/compress)."""
        with self._lock:
            if agent_id in self._caches:
                self._caches[agent_id].dirty = True

    def invalidate_all(self) -> None:
        """Invalida tutte le cache (dopo decay pass globale)."""
        with self._lock:
            for cache in self._caches.values():
                cache.dirty = True

    def load_vectors(self, agent_id: str, category: str | None = None) -> dict[int, list[float]]:
        """
        Carica/restituisce i vettori per un agente.
        Se la cache è dirty, ricarica dal DB.
        """
        cache = self.get_cache(agent_id)

        if cache.dirty:
            self._reload_from_db(agent_id, cache)

        return cache.vectors

    def search(
        self,
        query_vec: list[float],
        agent_id: str,
        category: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[tuple[int, float]]:
        """
        Ricerca vettoriale batch: calcola similarità coseno su tutti i vettori
        e restituisce i top-k risultati come [(memory_id, score), ...].

        Uses numpy batch dot product when available for ~10-50x speedup.
        Falls back to pure Python if numpy is not installed.
        """
        vectors = self.load_vectors(agent_id, category)
        if not vectors:
            return []

        mem_ids = list(vectors.keys())

        if _HAS_NUMPY and mem_ids:
            # Batch computation: build matrix and compute all dot products at once
            matrix = np.array([vectors[mid] for mid in mem_ids], dtype=np.float32)
            query_arr = np.array(query_vec, dtype=np.float32)
            similarities = matrix @ query_arr  # shape: (n,)

            scored: list[tuple[int, float]] = [
                (mem_ids[i], float(similarities[i]))
                for i in range(len(mem_ids))
                if similarities[i] >= min_similarity
            ]
        else:
            # Pure Python fallback
            scored = []
            for mem_id, vec in vectors.items():
                sim = sum(a * b for a, b in zip(query_vec, vec))
                if sim >= min_similarity:
                    scored.append((mem_id, sim))

        # Ordina per score decrescente e limita
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _reload_from_db(self, agent_id: str, cache: _AgentCache) -> None:
        """Ricarica tutti gli embeddings dal DB per l'agente."""
        from .database import get_connection
        from .embedder import deserialize

        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, embedding FROM memories
                WHERE embedding IS NOT NULL
                  AND compressed_into IS NULL
                  AND agent_id = ?
                """,
                (agent_id,),
            ).fetchall()

        cache.vectors = {}
        for row in rows:
            try:
                cache.vectors[row["id"]] = deserialize(row["embedding"])
            except Exception:
                continue  # embedding corrotto — skip

        cache.dirty = False


# Istanza globale — singleton
_index = VectorIndex()


def get_index() -> VectorIndex:
    return _index
