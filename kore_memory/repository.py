"""
Kore — Repository layer
All database operations, keeping business logic out of routes.
"""

import os
import threading
from datetime import UTC, datetime, timedelta

from .database import _get_db_path, get_connection
from .decay import compute_decay, effective_score, should_forget
from .events import (
    MEMORY_ARCHIVED,
    MEMORY_DECAYED,
    MEMORY_DELETED,
    MEMORY_RESTORED,
    MEMORY_SAVED,
    MEMORY_UPDATED,
    emit,
)
from .models import MemoryRecord, MemorySaveRequest, MemoryUpdateRequest
from .scorer import auto_score

_EMBEDDINGS_AVAILABLE: bool | None = None

# Lock for maintenance operations — prevents concurrent runs
_decay_lock = threading.Lock()
_compress_lock = threading.Lock()


def _embeddings_available() -> bool:
    global _EMBEDDINGS_AVAILABLE
    if _EMBEDDINGS_AVAILABLE is None:
        try:
            import sentence_transformers  # noqa: F401

            _EMBEDDINGS_AVAILABLE = True
        except ImportError:
            _EMBEDDINGS_AVAILABLE = False
    return _EMBEDDINGS_AVAILABLE


def save_memory(req: MemorySaveRequest, agent_id: str = "default", session_id: str | None = None) -> tuple[int, int]:
    """
    Persist a new memory record scoped to agent_id.
    Auto-scores importance if not explicitly set.
    Returns (row_id, importance).
    """
    importance = req.importance
    if importance is None:
        importance = auto_score(req.content, req.category)

    embedding_blob = None
    if _embeddings_available():
        from .embedder import embed, serialize

        try:
            embedding_blob = serialize(embed(req.content))
        except Exception:
            # Embedding failed — save anyway without embedding
            embedding_blob = None

    # Compute expires_at if TTL is specified
    expires_at = None
    if req.ttl_hours:
        expires_at = (datetime.now(UTC) + timedelta(hours=req.ttl_hours)).isoformat()

    with get_connection() as conn:
        # Auto-create session if session_id provided but doesn't exist
        if session_id:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, agent_id) VALUES (?, ?)",
                (session_id, agent_id),
            )

        cursor = conn.execute(
            """
            INSERT INTO memories (agent_id, content, category, importance, embedding, expires_at, session_id)
            VALUES (:agent_id, :content, :category, :importance, :embedding, :expires_at, :session_id)
            """,
            {
                "agent_id": agent_id,
                "content": req.content,
                "category": req.category,
                "importance": importance,
                "embedding": embedding_blob,
                "expires_at": expires_at,
                "session_id": session_id,
            },
        )
        row_id = cursor.lastrowid

    # Invalidate vector cache for the agent
    if embedding_blob:
        from .vector_index import get_index

        get_index().invalidate(agent_id)

    emit(MEMORY_SAVED, {"id": row_id, "agent_id": agent_id})

    # Entity extraction (optional, enabled via KORE_ENTITY_EXTRACTION=1)
    from . import config as _cfg

    if _cfg.ENTITY_EXTRACTION:
        from .integrations.entities import auto_tag_entities

        try:
            auto_tag_entities(row_id, req.content, agent_id)
        except Exception:
            pass  # graceful degradation

    return row_id, importance


def save_memory_batch(reqs: list[MemorySaveRequest], agent_id: str = "default") -> list[tuple[int, int]]:
    """
    Batch save: single transaction, batch embeddings.
    Returns list of (row_id, importance) tuples.
    """
    if not reqs:
        return []

    # Auto-score importances
    importances = []
    for req in reqs:
        imp = req.importance
        if imp is None:
            imp = auto_score(req.content, req.category)
        importances.append(imp)

    # Batch embed all contents at once
    embeddings: list[str | None] = [None] * len(reqs)
    if _embeddings_available():
        from .embedder import embed_batch, serialize

        try:
            vectors = embed_batch([req.content for req in reqs])
            embeddings = [serialize(v) for v in vectors]
        except Exception:
            pass  # Fall back to no embeddings

    # Single transaction for all inserts
    results = []
    with get_connection() as conn:
        for i, req in enumerate(reqs):
            expires_at = None
            if req.ttl_hours:
                expires_at = (datetime.now(UTC) + timedelta(hours=req.ttl_hours)).isoformat()

            cursor = conn.execute(
                """INSERT INTO memories (agent_id, content, category, importance, embedding, expires_at)
                   VALUES (:agent_id, :content, :category, :importance, :embedding, :expires_at)""",
                {
                    "agent_id": agent_id,
                    "content": req.content,
                    "category": req.category,
                    "importance": importances[i],
                    "embedding": embeddings[i],
                    "expires_at": expires_at,
                },
            )
            results.append((cursor.lastrowid, importances[i]))

    # Emit audit event for each saved memory
    for row_id, _ in results:
        emit(MEMORY_SAVED, {"id": row_id, "agent_id": agent_id})

    # Invalidate vector cache only once
    if any(e is not None for e in embeddings):
        from .vector_index import get_index

        get_index().invalidate(agent_id)

    return results


def search_memories(
    query: str,
    limit: int = 5,
    category: str | None = None,
    semantic: bool = True,
    agent_id: str = "default",
    cursor: tuple[float, int] | None = None,
) -> tuple[list[MemoryRecord], tuple[float, int] | None, int]:
    """
    Search memories with cursor-based pagination.

    Returns: (results, next_cursor, total_count)
    - results: list of MemoryRecord
    - next_cursor: (decay_score, id) for next page, or None if no more results
    - total_count: total matching memories in DB (not just page size)

    Uses semantic (embedding) search when available,
    falls back to FTS5 full-text search, then LIKE.
    Filters out fully-decayed memories. Reinforces access count on results.
    """
    # Fetch extra results to ensure we have enough after filtering
    fetch_limit = limit * 3

    if semantic and _embeddings_available():
        results = _semantic_search(query, fetch_limit, category, agent_id, cursor)
    else:
        results = _fts_search(query, fetch_limit, category, agent_id, cursor)

    # Filter forgotten memories, re-rank by combined score:
    # similarity (semantic) × decay × importance_weight
    alive = [r for r in results if not should_forget(r.decay_score or 1.0)]
    alive.sort(
        key=lambda r: (r.score if r.score and r.score > 0 else 1.0)
        * effective_score(r.decay_score or 1.0, r.importance),
        reverse=True,
    )

    # Get total count of matching active memories
    total_count = _count_active_memories(query, category, agent_id)

    # Take requested page + 1 to check if there are more results
    page = alive[: limit + 1]
    has_more = len(page) > limit
    top = page[:limit]

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and top:
        last = top[-1]
        next_cursor = (last.decay_score or 1.0, last.id)

    # Reinforce access for retrieved memories
    if top:
        _reinforce([r.id for r in top])

    return top, next_cursor, total_count


def update_memory(memory_id: int, req: MemoryUpdateRequest, agent_id: str = "default") -> bool:
    """
    Update an existing memory. Only provided fields are changed.
    Re-generates embedding if content changes.
    Returns True if updated, False if not found.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM memories WHERE id = ? AND agent_id = ? AND compressed_into IS NULL",
            (memory_id, agent_id),
        ).fetchone()
        if not row:
            return False

        updates = []
        params: list = []

        if req.content is not None:
            updates.append("content = ?")
            params.append(req.content)
            # Regenerate embedding if content changes
            if _embeddings_available():
                from .embedder import embed, serialize

                try:
                    embedding_blob = serialize(embed(req.content))
                    updates.append("embedding = ?")
                    params.append(embedding_blob)
                except Exception:
                    pass

        if req.category is not None:
            updates.append("category = ?")
            params.append(req.category)

        if req.importance is not None:
            updates.append("importance = ?")
            params.append(req.importance)

        if not updates:
            return True  # Nothing to update, but memory exists

        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(memory_id)
        params.append(agent_id)

        conn.execute(
            f"UPDATE memories SET {', '.join(updates)} WHERE id = ? AND agent_id = ?",
            params,
        )

    # Invalidate vector cache
    if req.content is not None:
        from .vector_index import get_index

        get_index().invalidate(agent_id)

    emit(MEMORY_UPDATED, {"id": memory_id, "agent_id": agent_id})
    return True


def get_memory(memory_id: int, agent_id: str = "default") -> MemoryRecord | None:
    """Recupera una singola memoria per ID, scoped all'agent. None se non trovata."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, content, category, importance, decay_score,
                      created_at, updated_at
               FROM memories
               WHERE id = ? AND agent_id = ? AND archived_at IS NULL""",
            (memory_id, agent_id),
        ).fetchone()
    if not row:
        return None
    return MemoryRecord(
        id=row["id"],
        content=row["content"],
        category=row["category"],
        importance=row["importance"],
        decay_score=row["decay_score"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def delete_memory(memory_id: int, agent_id: str = "default") -> bool:
    """Delete a memory by id, scoped to agent. Returns True if deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE id = ? AND agent_id = ?",
            (memory_id, agent_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        from .vector_index import get_index

        get_index().invalidate(agent_id)
        emit(MEMORY_DELETED, {"id": memory_id, "agent_id": agent_id})

    return deleted


def cleanup_expired(agent_id: str | None = None) -> int:
    """Delete memories with elapsed TTL. Returns the number of records removed."""
    with get_connection() as conn:
        sql = "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')"
        params: list = []
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(agent_id)
        cursor = conn.execute(sql, params)
        return cursor.rowcount


def run_decay_pass(agent_id: str | None = None) -> int:
    """
    Recalculate decay_score for all active memories (optionally scoped to agent).
    Also cleans up memories with elapsed TTL.
    Returns the count of memories updated. Thread-safe: only one run at a time.
    """
    if not _decay_lock.acquire(blocking=False):
        return 0  # run already in progress — silent skip

    try:
        # Clean up expired memories before recalculating
        cleanup_expired(agent_id)
        return _run_decay_pass_inner(agent_id)
    finally:
        _decay_lock.release()


def _run_decay_pass_inner(agent_id: str | None = None) -> int:
    with get_connection() as conn:
        sql = (
            "SELECT id, importance, created_at, last_accessed, access_count"
            " FROM memories WHERE compressed_into IS NULL AND archived_at IS NULL"
        )
        params: list = []
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(agent_id)
        rows = conn.execute(sql, params).fetchall()

    now = datetime.now(UTC).isoformat()
    updates = []
    for row in rows:
        new_score = compute_decay(
            importance=row["importance"],
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            access_count=row["access_count"],
        )
        updates.append((new_score, now, row["id"]))

    if updates:
        with get_connection() as conn:
            conn.executemany(
                "UPDATE memories SET decay_score = ?, updated_at = ? WHERE id = ?",
                updates,
            )
        emit(MEMORY_DECAYED, {"agent_id": agent_id or "all", "updated": len(updates)})

    return len(updates)


def get_timeline(
    subject: str,
    limit: int = 20,
    agent_id: str = "default",
    cursor: tuple[float, int] | None = None,
) -> tuple[list[MemoryRecord], tuple[float, int] | None, int]:
    """Return memories about a subject ordered by creation time with cursor pagination."""
    fetch_limit = limit * 2  # Fetch extra for sorting

    if _embeddings_available():
        results = _semantic_search(subject, fetch_limit, category=None, agent_id=agent_id, cursor=cursor)
    else:
        results = _fts_search(subject, fetch_limit, category=None, agent_id=agent_id, cursor=cursor)

    # Get total count
    total_count = _count_active_memories(subject, None, agent_id)

    # Sort by creation time (oldest first)
    sorted_results = sorted(results, key=lambda r: r.created_at)

    # Paginate
    page = sorted_results[: limit + 1]
    has_more = len(page) > limit
    top = page[:limit]

    next_cursor = None
    if has_more and top:
        last = top[-1]
        next_cursor = (last.decay_score or 1.0, last.id)

    return top, next_cursor, total_count


def export_memories(agent_id: str = "default") -> list[dict]:
    """Export all active memories for the agent as a list of dicts (without embeddings)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, content, category, importance, decay_score,
                   access_count, last_accessed, created_at, updated_at
            FROM memories
            WHERE agent_id = ? AND compressed_into IS NULL
              AND archived_at IS NULL
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC
            """,
            (agent_id,),
        ).fetchall()
    return [dict(r) for r in rows]


_VALID_CATEGORIES = {"general", "project", "trading", "finance", "person", "preference", "task", "decision"}


def import_memories(records: list[dict], agent_id: str = "default") -> int:
    """Import memories from a list of dicts. Returns the number of records imported."""
    imported = 0
    for rec in records:
        content = rec.get("content", "").strip()
        if not content or len(content) < 3:
            continue
        category = rec.get("category", "general")
        if category not in _VALID_CATEGORIES:
            category = "general"
        importance = rec.get("importance", 1)
        importance = max(1, min(5, int(importance)))

        req = MemorySaveRequest(
            content=content[:4000],
            category=category,
            importance=importance,
        )
        save_memory(req, agent_id=agent_id)
        imported += 1

    return imported


# ── Tag ──────────────────────────────────────────────────────────────────────


def add_tags(memory_id: int, tags: list[str], agent_id: str = "default") -> int:
    """Add tags to a memory. Returns the number of tags added."""
    # Verify that the memory belongs to the agent
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM memories WHERE id = ? AND agent_id = ?",
            (memory_id, agent_id),
        ).fetchone()
        if not row:
            return 0
        added = 0
        for tag in tags:
            tag = tag.strip().lower()[:100]
            if not tag:
                continue
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                    (memory_id, tag),
                )
                added += 1
            except Exception:
                continue
    return added


def remove_tags(memory_id: int, tags: list[str], agent_id: str = "default") -> int:
    """Remove tags from a memory. Returns the number of tags removed."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM memories WHERE id = ? AND agent_id = ?",
            (memory_id, agent_id),
        ).fetchone()
        if not row:
            return 0
        removed = 0
        for tag in tags:
            tag = tag.strip().lower()
            cursor = conn.execute(
                "DELETE FROM memory_tags WHERE memory_id = ? AND tag = ?",
                (memory_id, tag),
            )
            removed += cursor.rowcount
    return removed


def get_tags(memory_id: int, agent_id: str = "default") -> list[str]:
    """
    Return the tags of a memory.
    Verifies that the memory belongs to the specified agent_id.
    """
    with get_connection() as conn:
        # JOIN with memories to verify ownership
        rows = conn.execute(
            """
            SELECT mt.tag
            FROM memory_tags mt
            JOIN memories m ON mt.memory_id = m.id
            WHERE mt.memory_id = ? AND m.agent_id = ?
            ORDER BY mt.tag
            """,
            (memory_id, agent_id),
        ).fetchall()
    return [r["tag"] for r in rows]


def search_by_tag(tag: str, agent_id: str = "default", limit: int = 20) -> list[MemoryRecord]:
    """Search memories by tag."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.content, m.category, m.importance,
                   m.decay_score, m.access_count, m.last_accessed,
                   m.created_at, m.updated_at, NULL AS score
            FROM memories m
            JOIN memory_tags t ON m.id = t.memory_id
            WHERE t.tag = ? AND m.agent_id = ? AND m.compressed_into IS NULL
              AND m.archived_at IS NULL
              AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))
            ORDER BY m.importance DESC, m.created_at DESC
            LIMIT ?
            """,
            (tag.strip().lower(), agent_id, limit),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


# ── Relations ────────────────────────────────────────────────────────────────


def add_relation(source_id: int, target_id: int, relation: str = "related", agent_id: str = "default") -> bool:
    """Create a relation between two memories. Both must belong to the agent."""
    with get_connection() as conn:
        # Verify that both memories belong to the agent
        count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE id IN (?, ?) AND agent_id = ?",
            (source_id, target_id, agent_id),
        ).fetchone()[0]
        if count < 2:
            return False
        try:
            conn.execute(
                """INSERT OR IGNORE INTO memory_relations (source_id, target_id, relation)
                   VALUES (?, ?, ?)""",
                (source_id, target_id, relation.strip().lower()[:100]),
            )
            return True
        except Exception:
            return False


def get_relations(memory_id: int, agent_id: str = "default") -> list[dict]:
    """Return all relations of a memory (in both directions)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.source_id, r.target_id, r.relation, r.created_at,
                   m.content AS related_content
            FROM memory_relations r
            JOIN memories m ON m.id = CASE
                WHEN r.source_id = ? THEN r.target_id
                ELSE r.source_id
            END
            WHERE (r.source_id = ? OR r.target_id = ?) AND m.agent_id = ?
            ORDER BY r.created_at DESC
            """,
            (memory_id, memory_id, memory_id, agent_id),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Archive (soft-delete) ─────────────────────────────────────────────────────


def archive_memory(memory_id: int, agent_id: str = "default") -> bool:
    """Archive a memory (soft-delete). Returns True if archived."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE memories SET archived_at = datetime('now') WHERE id = ? AND agent_id = ? AND archived_at IS NULL",
            (memory_id, agent_id),
        )
        archived = cursor.rowcount > 0

    if archived:
        emit(MEMORY_ARCHIVED, {"id": memory_id, "agent_id": agent_id})

    return archived


def restore_memory(memory_id: int, agent_id: str = "default") -> bool:
    """Restore an archived memory. Returns True if restored."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE memories SET archived_at = NULL WHERE id = ? AND agent_id = ? AND archived_at IS NOT NULL",
            (memory_id, agent_id),
        )
        restored = cursor.rowcount > 0

    if restored:
        emit(MEMORY_RESTORED, {"id": memory_id, "agent_id": agent_id})

    return restored


def get_archived(agent_id: str = "default", limit: int = 50) -> list[MemoryRecord]:
    """List archived memories for an agent."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, content, category, importance, decay_score, access_count,
                      last_accessed, created_at, updated_at, NULL AS score
               FROM memories WHERE agent_id = ? AND archived_at IS NOT NULL
               ORDER BY archived_at DESC LIMIT ?""",
            (agent_id, limit),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


# ── Sessions ─────────────────────────────────────────────────────────────────


def create_session(session_id: str, agent_id: str = "default", title: str | None = None) -> dict:
    """Create a new conversation session."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, agent_id, title) VALUES (?, ?, ?)",
            (session_id, agent_id, title),
        )
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else {}


def list_sessions(agent_id: str = "default", limit: int = 50) -> list[dict]:
    """List all sessions for an agent with memory count."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.agent_id, s.title, s.created_at, s.ended_at,
                   COUNT(m.id) AS memory_count
            FROM sessions s
            LEFT JOIN memories m ON m.session_id = s.id AND m.agent_id = s.agent_id
            WHERE s.agent_id = ?
            GROUP BY s.id
            ORDER BY s.created_at DESC
            LIMIT ?
            """,
            (agent_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_memories(session_id: str, agent_id: str = "default") -> list[MemoryRecord]:
    """Get all memories in a session."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, content, category, importance, decay_score,
                   access_count, last_accessed, created_at, updated_at, NULL AS score
            FROM memories
            WHERE session_id = ? AND agent_id = ? AND compressed_into IS NULL
            ORDER BY created_at ASC
            """,
            (session_id, agent_id),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def end_session(session_id: str, agent_id: str = "default") -> bool:
    """Mark a session as ended."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET ended_at = datetime('now') WHERE id = ? AND agent_id = ? AND ended_at IS NULL",
            (session_id, agent_id),
        )
        return cursor.rowcount > 0


def delete_session(session_id: str, agent_id: str = "default") -> int:
    """Delete a session and unlink its memories. Returns number of memories unlinked."""
    with get_connection() as conn:
        # Unlink memories from session (don't delete them)
        cursor = conn.execute(
            "UPDATE memories SET session_id = NULL WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id),
        )
        unlinked = cursor.rowcount
        conn.execute(
            "DELETE FROM sessions WHERE id = ? AND agent_id = ?",
            (session_id, agent_id),
        )
    return unlinked


def get_session_summary(session_id: str, agent_id: str = "default") -> dict:
    """Get a summary of a session (no LLM, just aggregation)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND agent_id = ?",
            (session_id, agent_id),
        ).fetchone()
        if not row:
            return {}

        stats = conn.execute(
            """
            SELECT COUNT(*) AS memory_count,
                   GROUP_CONCAT(DISTINCT category) AS categories,
                   AVG(importance) AS avg_importance,
                   MIN(created_at) AS first_memory,
                   MAX(created_at) AS last_memory
            FROM memories
            WHERE session_id = ? AND agent_id = ? AND compressed_into IS NULL
            """,
            (session_id, agent_id),
        ).fetchone()

    return {
        "session_id": row["id"],
        "agent_id": row["agent_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "ended_at": row["ended_at"],
        "memory_count": stats["memory_count"] or 0,
        "categories": stats["categories"].split(",") if stats["categories"] else [],
        "avg_importance": round(stats["avg_importance"] or 0, 1),
        "first_memory": stats["first_memory"],
        "last_memory": stats["last_memory"],
    }


# ── Agents ───────────────────────────────────────────────────────────────────


def list_agents() -> list[dict]:
    """Return all distinct agent_ids with memory count and last activity."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT agent_id,
                   COUNT(*) AS memory_count,
                   MAX(created_at) AS last_active
            FROM memories
            WHERE compressed_into IS NULL
            GROUP BY agent_id
            ORDER BY last_active DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


# ── Stats / Metrics ──────────────────────────────────────────────────────────


def get_stats(agent_id: str | None = None) -> dict:
    """Get database statistics for monitoring."""
    with get_connection() as conn:
        if agent_id:
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND compressed_into IS NULL",
                (agent_id,),
            ).fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND compressed_into IS NULL AND decay_score >= 0.05",
                (agent_id,),
            ).fetchone()[0]
            try:
                archived = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND archived_at IS NOT NULL",
                    (agent_id,),
                ).fetchone()[0]
            except Exception:
                archived = 0
        else:
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE compressed_into IS NULL",
            ).fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE compressed_into IS NULL AND decay_score >= 0.05",
            ).fetchone()[0]
            try:
                archived = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE archived_at IS NOT NULL",
                ).fetchone()[0]
            except Exception:
                archived = 0

        db_path = _get_db_path()
        db_size = os.path.getsize(str(db_path)) if db_path.exists() else 0

    return {"total_memories": total, "active_memories": active, "archived_memories": archived, "db_size_bytes": db_size}


# ── Private helpers ──────────────────────────────────────────────────────────


def _count_active_memories(query: str, category: str | None, agent_id: str) -> int:
    """Count total active memories matching query (for pagination total)."""
    with get_connection() as conn:
        safe_query = _sanitize_fts_query(query)
        if safe_query:
            sql = """
                SELECT COUNT(*) FROM memories_fts
                JOIN memories m ON memories_fts.rowid = m.id
                WHERE memories_fts MATCH :query
                  AND m.agent_id = :agent_id
                  AND m.compressed_into IS NULL
                  AND m.archived_at IS NULL
                  AND m.decay_score >= 0.05
                  AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))
            """
            params: dict = {"query": safe_query, "agent_id": agent_id}
        else:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            sql = """
                SELECT COUNT(*) FROM memories
                WHERE content LIKE :query ESCAPE '\\'
                  AND agent_id = :agent_id
                  AND compressed_into IS NULL
                  AND archived_at IS NULL
                  AND decay_score >= 0.05
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
            """
            params = {"query": f"%{escaped}%", "agent_id": agent_id}

        if category:
            # Prefix m. for FTS JOIN, no prefix for direct LIKE query
            col_prefix = "m." if safe_query else ""
            sql = sql.rstrip() + f" AND {col_prefix}category = :category"
            params["category"] = category

        return conn.execute(sql, params).fetchone()[0]


def _reinforce(memory_ids: list[int]) -> None:
    """Increment access_count and update last_accessed for retrieved memories."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.executemany(
            """
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed = ?,
                decay_score   = MIN(1.0, decay_score + 0.05),
                updated_at    = ?
            WHERE id = ?
            """,
            [(now, now, mid) for mid in memory_ids],
        )


def _fts_search(
    query: str,
    limit: int,
    category: str | None,
    agent_id: str = "default",
    cursor: tuple[float, int] | None = None,
) -> list[MemoryRecord]:
    """Full-text search via SQLite FTS5 with prefix wildcards, scoped to agent."""
    with get_connection() as conn:
        safe_query = _sanitize_fts_query(query)

        cursor_filter = ""
        if cursor:
            decay_score, last_id = cursor
            cursor_filter = (
                "AND ((m.decay_score, m.id) < (:cursor_score, :cursor_id))"
                if safe_query
                else "AND ((decay_score, id) < (:cursor_score, :cursor_id))"
            )

        if safe_query:
            sql = """
                SELECT m.id, m.content, m.category, m.importance,
                       m.decay_score, m.access_count, m.last_accessed,
                       m.created_at, m.updated_at, rank AS score
                FROM memories_fts
                JOIN memories m ON memories_fts.rowid = m.id
                WHERE memories_fts MATCH :query
                  AND m.agent_id = :agent_id
                  AND m.compressed_into IS NULL
                  AND m.archived_at IS NULL
                  AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))
                  {category_filter}
                  {cursor_filter}
                ORDER BY m.decay_score DESC, m.id DESC
                LIMIT :limit
            """
            params: dict = {"query": safe_query, "limit": limit, "agent_id": agent_id}
        else:
            sql = """
                SELECT id, content, category, importance,
                       decay_score, access_count, last_accessed,
                       created_at, updated_at, NULL AS score
                FROM memories
                WHERE content LIKE :query ESCAPE '\\'
                  AND agent_id = :agent_id
                  AND compressed_into IS NULL
                  AND archived_at IS NULL
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
                  {category_filter}
                  {cursor_filter}
                ORDER BY decay_score DESC, id DESC
                LIMIT :limit
            """
            # q=* → list all memories (global wildcard)
            if query.strip() == "*":
                escaped_query = ""
            else:
                escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params = {"query": f"%{escaped_query}%", "limit": limit, "agent_id": agent_id}

        if cursor:
            params["cursor_score"] = cursor[0]
            params["cursor_id"] = cursor[1]

        category_filter = (
            "AND m.category = :category" if safe_query and category else "AND category = :category" if category else ""
        )
        if category:
            params["category"] = category

        rows = conn.execute(sql.format(category_filter=category_filter, cursor_filter=cursor_filter), params).fetchall()

    return [_row_to_record(r) for r in rows]


def _semantic_search(
    query: str,
    limit: int,
    category: str | None,
    agent_id: str = "default",
    cursor: tuple[float, int] | None = None,
) -> list[MemoryRecord]:
    """Semantic search with in-memory vector index, scoped to agent."""
    from .embedder import embed
    from .vector_index import get_index

    query_vec = embed(query)
    index = get_index()

    # Batch vector search via in-memory index
    top_ids = index.search(query_vec, agent_id, category=category, limit=limit)
    if not top_ids:
        return []

    # Load full records from DB with cursor filter
    id_score_map = {mem_id: score for mem_id, score in top_ids}
    placeholders = ",".join("?" for _ in top_ids)

    cursor_filter = ""
    params = [id for id, _ in top_ids]

    with get_connection() as conn:
        # Build query — parameter order: IN ids, category, cursor
        category_clause = "AND category = ?" if category else ""
        if category:
            params.append(category)

        if cursor:
            decay_score, last_id = cursor
            cursor_filter = "AND ((decay_score, id) < (?, ?))"
            params.extend([decay_score, last_id])

        sql = f"""
            SELECT id, content, category, importance,
                   decay_score, access_count, last_accessed,
                   created_at, updated_at
            FROM memories
            WHERE id IN ({placeholders})
              AND archived_at IS NULL
              AND (expires_at IS NULL OR expires_at > datetime('now'))
              {category_clause}
              {cursor_filter}
            ORDER BY decay_score DESC, id DESC
        """
        rows = conn.execute(sql, params).fetchall()

    results = []
    for row in rows:
        sim = id_score_map.get(row["id"], 0.0)
        results.append(
            MemoryRecord(
                id=row["id"],
                content=row["content"],
                category=row["category"],
                importance=row["importance"],
                decay_score=row["decay_score"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                score=round(sim, 4),
            )
        )

    # Sort by descending score
    results.sort(key=lambda r: r.score or 0.0, reverse=True)
    return results


def _sanitize_fts_query(query: str) -> str:
    """Sanitize FTS5 query: remove special operators, limit token count."""
    special = set('"^():-*+<>&|')
    cleaned = "".join(c if c not in special else " " for c in query).strip()
    if not cleaned:
        return ""
    # Max 10 tokens, min 2 characters each — prevents DoS
    tokens = [t for t in cleaned.split() if len(t) >= 2][:10]
    if not tokens:
        return ""
    # Quote for exact match, wildcard suffix for flexibility
    return " OR ".join(f'"{t}"*' for t in tokens)


def _row_to_record(row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        content=row["content"],
        category=row["category"],
        importance=row["importance"],
        decay_score=row["decay_score"] if "decay_score" in row.keys() else 1.0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        score=row["score"],
    )
