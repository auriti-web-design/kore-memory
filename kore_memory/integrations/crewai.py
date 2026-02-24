"""
Kore Memory — CrewAI integration.
Provides KoreCrewAIMemory as a memory provider for CrewAI agents.

Usage:
    from kore_memory.integrations.crewai import KoreCrewAIMemory

    memory = KoreCrewAIMemory(base_url="http://localhost:8765", agent_id="my-crew")
    memory.save("The user prefers dark mode")
    results = memory.search("user preferences")
"""

from __future__ import annotations

from typing import Any

try:
    from crewai.memory import BaseMemory as CrewAIBaseMemory

    _HAS_CREWAI = True
except ImportError:
    _HAS_CREWAI = False
    CrewAIBaseMemory = object  # type: ignore[assignment, misc]


from kore_memory.client import KoreClient


class KoreCrewAIMemory(CrewAIBaseMemory):  # type: ignore[misc]
    """
    CrewAI memory provider backed by Kore Memory.

    Wraps KoreClient to store and retrieve memories through the Kore Memory API.
    Supports short-term (ephemeral, high-decay) and long-term (persistent, high-importance)
    memory patterns.

    Args:
        base_url: URL del server Kore (default: http://localhost:8765)
        api_key: API key per autenticazione (opzionale su localhost)
        agent_id: Namespace agente per isolamento memorie (default: "default")
        category: Categoria default per le memorie salvate (default: "general")
        timeout: Timeout richieste in secondi (default: 10.0)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        api_key: str | None = None,
        agent_id: str = "default",
        category: str = "general",
        timeout: float = 10.0,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._agent_id = agent_id
        self._category = category
        self._timeout = timeout
        self._client = KoreClient(
            base_url=base_url,
            api_key=api_key,
            agent_id=agent_id,
            timeout=timeout,
        )

    # ── Core interface ───────────────────────────────────────────────────

    def save(self, value: str, metadata: dict[str, Any] | None = None) -> None:
        """
        Salva una memoria in Kore.

        Args:
            value: Contenuto testuale della memoria.
            metadata: Dict opzionale con chiavi extra (category, importance, ttl_hours).
                      Le chiavi riconosciute vengono estratte e passate a KoreClient.save().
        """
        meta = metadata or {}
        category = meta.get("category", self._category)
        importance = meta.get("importance", 1)
        ttl_hours = meta.get("ttl_hours", None)

        self._client.save(
            content=value,
            category=category,
            importance=importance,
            ttl_hours=ttl_hours,
        )

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Cerca memorie in Kore.

        Args:
            query: Stringa di ricerca (FTS5 o semantic).
            limit: Numero massimo di risultati (default: 5).

        Returns:
            Lista di dict con id, content, category, importance, decay_score, score.
        """
        response = self._client.search(q=query, limit=limit, category=None, semantic=True)
        return [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "decay_score": r.decay_score,
                "score": r.score,
            }
            for r in response.results
        ]

    # ── Short-term / Long-term patterns ──────────────────────────────────

    def save_short_term(self, value: str) -> None:
        """
        Salva una memoria a breve termine (alta decay, bassa importanza).
        TTL di 24 ore, importance 1 — verra dimenticata rapidamente.
        """
        self.save(value, metadata={"importance": 1, "ttl_hours": 24})

    def save_long_term(self, value: str, importance: int = 4) -> None:
        """
        Salva una memoria a lungo termine (alta importanza, nessun TTL).
        Importance default 4, decay naturale via curva di Ebbinghaus.

        Args:
            value: Contenuto testuale della memoria.
            importance: Livello di importanza 2-5 (default: 4).
        """
        clamped = max(2, min(5, importance))
        self.save(value, metadata={"importance": clamped})

    # ── Lifecycle ────────────────────────────────────────────────────────

    def close(self) -> None:
        """Chiude il client HTTP sottostante."""
        self._client.close()

    def __enter__(self) -> KoreCrewAIMemory:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"KoreCrewAIMemory(base_url={self._base_url!r}, "
            f"agent_id={self._agent_id!r}, category={self._category!r})"
        )
