"""
Kore — Python SDK Client
Client type-safe per interagire con il server Kore via HTTP.
Supporta sia uso sincrono (KoreClient) che asincrono (AsyncKoreClient).

Uso:
    from kore_memory import KoreClient

    with KoreClient("http://localhost:8765", api_key="...") as kore:
        kore.save("Ricordo importante", category="project", importance=4)
        results = kore.search("progetto")
"""

from __future__ import annotations

from typing import Any

import httpx

from .models import (
    BatchSaveResponse,
    CleanupExpiredResponse,
    CompressRunResponse,
    DecayRunResponse,
    MemoryExportResponse,
    MemoryImportResponse,
    MemorySaveResponse,
    MemorySearchResponse,
    RelationResponse,
    TagResponse,
)


# ── Eccezioni ────────────────────────────────────────────────────────────────


class KoreError(Exception):
    """Errore base per il client Kore."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class KoreAuthError(KoreError):
    """Autenticazione fallita (401/403)."""


class KoreNotFoundError(KoreError):
    """Risorsa non trovata (404)."""


class KoreRateLimitError(KoreError):
    """Rate limit superato (429)."""


class KoreServerError(KoreError):
    """Errore lato server (5xx)."""


class KoreValidationError(KoreError):
    """Validazione fallita (422)."""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _raise_for_status(response: httpx.Response) -> None:
    """Converte errori HTTP in eccezioni Kore tipizzate."""
    if response.is_success:
        return

    status = response.status_code
    try:
        body = response.json()
        detail = body.get("detail", body)
    except Exception:
        detail = response.text

    if status == 401:
        raise KoreAuthError("Authentication required", status, detail)
    if status == 403:
        raise KoreAuthError("Invalid API key", status, detail)
    if status == 404:
        raise KoreNotFoundError("Resource not found", status, detail)
    if status == 422:
        raise KoreValidationError("Validation error", status, detail)
    if status == 429:
        raise KoreRateLimitError("Rate limit exceeded", status, detail)
    if status >= 500:
        raise KoreServerError("Server error", status, detail)

    raise KoreError(f"HTTP {status}", status, detail)


def _build_headers(api_key: str | None, agent_id: str) -> dict[str, str]:
    """Costruisce gli header comuni per le richieste."""
    headers: dict[str, str] = {"X-Agent-Id": agent_id}
    if api_key:
        headers["X-Kore-Key"] = api_key
    return headers


# ── Client sincrono ──────────────────────────────────────────────────────────


class KoreClient:
    """
    Client sincrono per Kore Memory API.

    Args:
        base_url: URL del server Kore (default: http://localhost:8765)
        api_key: API key per autenticazione (opzionale su localhost)
        agent_id: Namespace agente (default: "default")
        timeout: Timeout richieste in secondi (default: 10.0)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        api_key: str | None = None,
        agent_id: str = "default",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=_build_headers(api_key, agent_id),
            timeout=timeout,
        )

    def __enter__(self) -> KoreClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Chiude il client HTTP."""
        self._client.close()

    # ── Core ─────────────────────────────────────────────────────────────

    def save(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
        ttl_hours: int | None = None,
    ) -> MemorySaveResponse:
        """Salva una memoria. Importance auto-calcolata se 1."""
        payload: dict[str, Any] = {
            "content": content,
            "category": category,
            "importance": importance,
        }
        if ttl_hours is not None:
            payload["ttl_hours"] = ttl_hours
        r = self._client.post("/save", json=payload)
        _raise_for_status(r)
        return MemorySaveResponse(**r.json())

    def save_batch(
        self,
        memories: list[dict[str, Any]],
    ) -> BatchSaveResponse:
        """Salva fino a 100 memorie in una sola richiesta."""
        r = self._client.post("/save/batch", json={"memories": memories})
        _raise_for_status(r)
        return BatchSaveResponse(**r.json())

    def search(
        self,
        q: str,
        limit: int = 5,
        offset: int = 0,
        category: str | None = None,
        semantic: bool = True,
    ) -> MemorySearchResponse:
        """Cerca memorie per significato o testo."""
        params: dict[str, Any] = {
            "q": q,
            "limit": limit,
            "offset": offset,
            "semantic": semantic,
        }
        if category:
            params["category"] = category
        r = self._client.get("/search", params=params)
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    def timeline(
        self,
        subject: str,
        limit: int = 20,
        offset: int = 0,
    ) -> MemorySearchResponse:
        """Cronologia memorie su un argomento (dal più vecchio al più recente)."""
        r = self._client.get("/timeline", params={
            "subject": subject,
            "limit": limit,
            "offset": offset,
        })
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    def delete(self, memory_id: int) -> bool:
        """Elimina una memoria. Restituisce True se eliminata."""
        r = self._client.delete(f"/memories/{memory_id}")
        if r.status_code == 404:
            return False
        _raise_for_status(r)
        return True

    # ── Tags ─────────────────────────────────────────────────────────────

    def add_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Aggiunge tag a una memoria."""
        r = self._client.post(f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    def get_tags(self, memory_id: int) -> TagResponse:
        """Restituisce i tag di una memoria."""
        r = self._client.get(f"/memories/{memory_id}/tags")
        _raise_for_status(r)
        return TagResponse(**r.json())

    def remove_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Rimuove tag da una memoria."""
        r = self._client.request("DELETE", f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    def search_by_tag(self, tag: str, limit: int = 20) -> MemorySearchResponse:
        """Cerca memorie per tag."""
        r = self._client.get(f"/tags/{tag}/memories", params={"limit": limit})
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    # ── Relations ────────────────────────────────────────────────────────

    def add_relation(
        self,
        memory_id: int,
        target_id: int,
        relation: str = "related",
    ) -> RelationResponse:
        """Crea una relazione tra due memorie."""
        r = self._client.post(f"/memories/{memory_id}/relations", json={
            "target_id": target_id,
            "relation": relation,
        })
        _raise_for_status(r)
        return RelationResponse(**r.json())

    def get_relations(self, memory_id: int) -> RelationResponse:
        """Restituisce le relazioni di una memoria."""
        r = self._client.get(f"/memories/{memory_id}/relations")
        _raise_for_status(r)
        return RelationResponse(**r.json())

    # ── Maintenance ──────────────────────────────────────────────────────

    def decay_run(self) -> DecayRunResponse:
        """Ricalcola i decay score delle memorie."""
        r = self._client.post("/decay/run")
        _raise_for_status(r)
        return DecayRunResponse(**r.json())

    def compress(self) -> CompressRunResponse:
        """Unisce memorie simili."""
        r = self._client.post("/compress")
        _raise_for_status(r)
        return CompressRunResponse(**r.json())

    def cleanup(self) -> CleanupExpiredResponse:
        """Rimuove memorie con TTL scaduto."""
        r = self._client.post("/cleanup")
        _raise_for_status(r)
        return CleanupExpiredResponse(**r.json())

    # ── Backup ───────────────────────────────────────────────────────────

    def export_memories(self) -> MemoryExportResponse:
        """Esporta tutte le memorie attive in JSON."""
        r = self._client.get("/export")
        _raise_for_status(r)
        return MemoryExportResponse(**r.json())

    def import_memories(self, memories: list[dict[str, Any]]) -> MemoryImportResponse:
        """Importa memorie da una lista di dict."""
        r = self._client.post("/import", json={"memories": memories})
        _raise_for_status(r)
        return MemoryImportResponse(**r.json())

    # ── Utility ──────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Health check del server."""
        r = self._client.get("/health")
        _raise_for_status(r)
        return r.json()


# ── Client asincrono ─────────────────────────────────────────────────────────


class AsyncKoreClient:
    """
    Client asincrono per Kore Memory API.

    Args:
        base_url: URL del server Kore (default: http://localhost:8765)
        api_key: API key per autenticazione (opzionale su localhost)
        agent_id: Namespace agente (default: "default")
        timeout: Timeout richieste in secondi (default: 10.0)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        api_key: str | None = None,
        agent_id: str = "default",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=_build_headers(api_key, agent_id),
            timeout=timeout,
        )

    async def __aenter__(self) -> AsyncKoreClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Chiude il client HTTP."""
        await self._client.aclose()

    # ── Core ─────────────────────────────────────────────────────────────

    async def save(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
        ttl_hours: int | None = None,
    ) -> MemorySaveResponse:
        """Salva una memoria. Importance auto-calcolata se 1."""
        payload: dict[str, Any] = {
            "content": content,
            "category": category,
            "importance": importance,
        }
        if ttl_hours is not None:
            payload["ttl_hours"] = ttl_hours
        r = await self._client.post("/save", json=payload)
        _raise_for_status(r)
        return MemorySaveResponse(**r.json())

    async def save_batch(
        self,
        memories: list[dict[str, Any]],
    ) -> BatchSaveResponse:
        """Salva fino a 100 memorie in una sola richiesta."""
        r = await self._client.post("/save/batch", json={"memories": memories})
        _raise_for_status(r)
        return BatchSaveResponse(**r.json())

    async def search(
        self,
        q: str,
        limit: int = 5,
        offset: int = 0,
        category: str | None = None,
        semantic: bool = True,
    ) -> MemorySearchResponse:
        """Cerca memorie per significato o testo."""
        params: dict[str, Any] = {
            "q": q,
            "limit": limit,
            "offset": offset,
            "semantic": semantic,
        }
        if category:
            params["category"] = category
        r = await self._client.get("/search", params=params)
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    async def timeline(
        self,
        subject: str,
        limit: int = 20,
        offset: int = 0,
    ) -> MemorySearchResponse:
        """Cronologia memorie su un argomento (dal più vecchio al più recente)."""
        r = await self._client.get("/timeline", params={
            "subject": subject,
            "limit": limit,
            "offset": offset,
        })
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    async def delete(self, memory_id: int) -> bool:
        """Elimina una memoria. Restituisce True se eliminata."""
        r = await self._client.delete(f"/memories/{memory_id}")
        if r.status_code == 404:
            return False
        _raise_for_status(r)
        return True

    # ── Tags ─────────────────────────────────────────────────────────────

    async def add_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Aggiunge tag a una memoria."""
        r = await self._client.post(f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    async def get_tags(self, memory_id: int) -> TagResponse:
        """Restituisce i tag di una memoria."""
        r = await self._client.get(f"/memories/{memory_id}/tags")
        _raise_for_status(r)
        return TagResponse(**r.json())

    async def remove_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Rimuove tag da una memoria."""
        r = await self._client.request("DELETE", f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    async def search_by_tag(self, tag: str, limit: int = 20) -> MemorySearchResponse:
        """Cerca memorie per tag."""
        r = await self._client.get(f"/tags/{tag}/memories", params={"limit": limit})
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    # ── Relations ────────────────────────────────────────────────────────

    async def add_relation(
        self,
        memory_id: int,
        target_id: int,
        relation: str = "related",
    ) -> RelationResponse:
        """Crea una relazione tra due memorie."""
        r = await self._client.post(f"/memories/{memory_id}/relations", json={
            "target_id": target_id,
            "relation": relation,
        })
        _raise_for_status(r)
        return RelationResponse(**r.json())

    async def get_relations(self, memory_id: int) -> RelationResponse:
        """Restituisce le relazioni di una memoria."""
        r = await self._client.get(f"/memories/{memory_id}/relations")
        _raise_for_status(r)
        return RelationResponse(**r.json())

    # ── Maintenance ──────────────────────────────────────────────────────

    async def decay_run(self) -> DecayRunResponse:
        """Ricalcola i decay score delle memorie."""
        r = await self._client.post("/decay/run")
        _raise_for_status(r)
        return DecayRunResponse(**r.json())

    async def compress(self) -> CompressRunResponse:
        """Unisce memorie simili."""
        r = await self._client.post("/compress")
        _raise_for_status(r)
        return CompressRunResponse(**r.json())

    async def cleanup(self) -> CleanupExpiredResponse:
        """Rimuove memorie con TTL scaduto."""
        r = await self._client.post("/cleanup")
        _raise_for_status(r)
        return CleanupExpiredResponse(**r.json())

    # ── Backup ───────────────────────────────────────────────────────────

    async def export_memories(self) -> MemoryExportResponse:
        """Esporta tutte le memorie attive in JSON."""
        r = await self._client.get("/export")
        _raise_for_status(r)
        return MemoryExportResponse(**r.json())

    async def import_memories(self, memories: list[dict[str, Any]]) -> MemoryImportResponse:
        """Importa memorie da una lista di dict."""
        r = await self._client.post("/import", json={"memories": memories})
        _raise_for_status(r)
        return MemoryImportResponse(**r.json())

    # ── Utility ──────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Health check del server."""
        r = await self._client.get("/health")
        _raise_for_status(r)
        return r.json()
