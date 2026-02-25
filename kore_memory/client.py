"""
Kore — Python SDK Client
Type-safe client for interacting with the Kore server via HTTP.
Supports both synchronous (KoreClient) and asynchronous (AsyncKoreClient) usage.

Usage:
    from kore_memory import KoreClient

    with KoreClient("http://localhost:8765", api_key="...") as kore:
        kore.save("Important memory", category="project", importance=4)
        results = kore.search("project")
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

# ── Exceptions ───────────────────────────────────────────────────────────────


class KoreError(Exception):
    """Base error class for the Kore client."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class KoreAuthError(KoreError):
    """Authentication failed (401/403)."""


class KoreNotFoundError(KoreError):
    """Resource not found (404)."""


class KoreRateLimitError(KoreError):
    """Rate limit exceeded (429)."""


class KoreServerError(KoreError):
    """Server-side error (5xx)."""


class KoreValidationError(KoreError):
    """Validation failed (422)."""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _raise_for_status(response: httpx.Response) -> None:
    """Converts HTTP errors into typed Kore exceptions."""
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
    """Builds the common request headers."""
    headers: dict[str, str] = {"X-Agent-Id": agent_id}
    if api_key:
        headers["X-Kore-Key"] = api_key
    return headers


# ── Synchronous client ───────────────────────────────────────────────────────


class KoreClient:
    """
    Synchronous client for the Kore Memory API.

    Args:
        base_url: Kore server URL (default: http://localhost:8765)
        api_key: API key for authentication (optional on localhost)
        agent_id: Agent namespace (default: "default")
        timeout: Request timeout in seconds (default: 10.0)
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
        """Closes the HTTP client."""
        self._client.close()

    # ── Core ─────────────────────────────────────────────────────────────

    def save(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
        ttl_hours: int | None = None,
    ) -> MemorySaveResponse:
        """Saves a memory. Importance is auto-calculated when set to 1."""
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
        """Saves up to 100 memories in a single request."""
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
        """Searches memories by meaning or text."""
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
        """Returns the memory timeline for a subject (oldest to newest)."""
        r = self._client.get(
            "/timeline",
            params={
                "subject": subject,
                "limit": limit,
                "offset": offset,
            },
        )
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    def delete(self, memory_id: int) -> bool:
        """Deletes a memory. Returns True if deleted."""
        r = self._client.delete(f"/memories/{memory_id}")
        if r.status_code == 404:
            return False
        _raise_for_status(r)
        return True

    # ── Tags ─────────────────────────────────────────────────────────────

    def add_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Adds tags to a memory."""
        r = self._client.post(f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    def get_tags(self, memory_id: int) -> TagResponse:
        """Returns the tags of a memory."""
        r = self._client.get(f"/memories/{memory_id}/tags")
        _raise_for_status(r)
        return TagResponse(**r.json())

    def remove_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Removes tags from a memory."""
        r = self._client.request("DELETE", f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    def search_by_tag(self, tag: str, limit: int = 20) -> MemorySearchResponse:
        """Searches memories by tag."""
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
        """Creates a relation between two memories."""
        r = self._client.post(
            f"/memories/{memory_id}/relations",
            json={
                "target_id": target_id,
                "relation": relation,
            },
        )
        _raise_for_status(r)
        return RelationResponse(**r.json())

    def get_relations(self, memory_id: int) -> RelationResponse:
        """Returns the relations of a memory."""
        r = self._client.get(f"/memories/{memory_id}/relations")
        _raise_for_status(r)
        return RelationResponse(**r.json())

    # ── Maintenance ──────────────────────────────────────────────────────

    def decay_run(self) -> DecayRunResponse:
        """Recalculates the decay scores of all memories."""
        r = self._client.post("/decay/run")
        _raise_for_status(r)
        return DecayRunResponse(**r.json())

    def compress(self) -> CompressRunResponse:
        """Merges similar memories."""
        r = self._client.post("/compress")
        _raise_for_status(r)
        return CompressRunResponse(**r.json())

    def cleanup(self) -> CleanupExpiredResponse:
        """Removes memories with an expired TTL."""
        r = self._client.post("/cleanup")
        _raise_for_status(r)
        return CleanupExpiredResponse(**r.json())

    # ── Backup ───────────────────────────────────────────────────────────

    def export_memories(self) -> MemoryExportResponse:
        """Exports all active memories as JSON."""
        r = self._client.get("/export")
        _raise_for_status(r)
        return MemoryExportResponse(**r.json())

    def import_memories(self, memories: list[dict[str, Any]]) -> MemoryImportResponse:
        """Imports memories from a list of dicts."""
        r = self._client.post("/import", json={"memories": memories})
        _raise_for_status(r)
        return MemoryImportResponse(**r.json())

    # ── Utility ──────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Server health check."""
        r = self._client.get("/health")
        _raise_for_status(r)
        return r.json()


# ── Asynchronous client ──────────────────────────────────────────────────────


class AsyncKoreClient:
    """
    Asynchronous client for the Kore Memory API.

    Args:
        base_url: Kore server URL (default: http://localhost:8765)
        api_key: API key for authentication (optional on localhost)
        agent_id: Agent namespace (default: "default")
        timeout: Request timeout in seconds (default: 10.0)
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
        """Closes the HTTP client."""
        await self._client.aclose()

    # ── Core ─────────────────────────────────────────────────────────────

    async def save(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
        ttl_hours: int | None = None,
    ) -> MemorySaveResponse:
        """Saves a memory. Importance is auto-calculated when set to 1."""
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
        """Saves up to 100 memories in a single request."""
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
        """Searches memories by meaning or text."""
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
        """Returns the memory timeline for a subject (oldest to newest)."""
        r = await self._client.get(
            "/timeline",
            params={
                "subject": subject,
                "limit": limit,
                "offset": offset,
            },
        )
        _raise_for_status(r)
        return MemorySearchResponse(**r.json())

    async def delete(self, memory_id: int) -> bool:
        """Deletes a memory. Returns True if deleted."""
        r = await self._client.delete(f"/memories/{memory_id}")
        if r.status_code == 404:
            return False
        _raise_for_status(r)
        return True

    # ── Tags ─────────────────────────────────────────────────────────────

    async def add_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Adds tags to a memory."""
        r = await self._client.post(f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    async def get_tags(self, memory_id: int) -> TagResponse:
        """Returns the tags of a memory."""
        r = await self._client.get(f"/memories/{memory_id}/tags")
        _raise_for_status(r)
        return TagResponse(**r.json())

    async def remove_tags(self, memory_id: int, tags: list[str]) -> TagResponse:
        """Removes tags from a memory."""
        r = await self._client.request("DELETE", f"/memories/{memory_id}/tags", json={"tags": tags})
        _raise_for_status(r)
        return TagResponse(**r.json())

    async def search_by_tag(self, tag: str, limit: int = 20) -> MemorySearchResponse:
        """Searches memories by tag."""
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
        """Creates a relation between two memories."""
        r = await self._client.post(
            f"/memories/{memory_id}/relations",
            json={
                "target_id": target_id,
                "relation": relation,
            },
        )
        _raise_for_status(r)
        return RelationResponse(**r.json())

    async def get_relations(self, memory_id: int) -> RelationResponse:
        """Returns the relations of a memory."""
        r = await self._client.get(f"/memories/{memory_id}/relations")
        _raise_for_status(r)
        return RelationResponse(**r.json())

    # ── Maintenance ──────────────────────────────────────────────────────

    async def decay_run(self) -> DecayRunResponse:
        """Recalculates the decay scores of all memories."""
        r = await self._client.post("/decay/run")
        _raise_for_status(r)
        return DecayRunResponse(**r.json())

    async def compress(self) -> CompressRunResponse:
        """Merges similar memories."""
        r = await self._client.post("/compress")
        _raise_for_status(r)
        return CompressRunResponse(**r.json())

    async def cleanup(self) -> CleanupExpiredResponse:
        """Removes memories with an expired TTL."""
        r = await self._client.post("/cleanup")
        _raise_for_status(r)
        return CleanupExpiredResponse(**r.json())

    # ── Backup ───────────────────────────────────────────────────────────

    async def export_memories(self) -> MemoryExportResponse:
        """Exports all active memories as JSON."""
        r = await self._client.get("/export")
        _raise_for_status(r)
        return MemoryExportResponse(**r.json())

    async def import_memories(self, memories: list[dict[str, Any]]) -> MemoryImportResponse:
        """Imports memories from a list of dicts."""
        r = await self._client.post("/import", json={"memories": memories})
        _raise_for_status(r)
        return MemoryImportResponse(**r.json())

    # ── Utility ──────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Server health check."""
        r = await self._client.get("/health")
        _raise_for_status(r)
        return r.json()
