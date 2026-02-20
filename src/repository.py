"""
Kore — Repository layer
All database operations, keeping business logic out of routes.
"""

import threading
from datetime import datetime, timezone

from .database import get_connection
from .decay import compute_decay, effective_score, should_forget
from .models import MemoryRecord, MemorySaveRequest
from .scorer import auto_score

_EMBEDDINGS_AVAILABLE: bool | None = None

# Lock per operazioni di manutenzione — previene run concorrenti
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


def save_memory(req: MemorySaveRequest, agent_id: str = "default") -> tuple[int, int]:
    """
    Persist a new memory record scoped to agent_id.
    Auto-scores importance if not explicitly set.
    Returns (row_id, importance).
    """
    importance = req.importance
    if importance == 1:
        importance = auto_score(req.content, req.category)

    embedding_blob = None
    if _embeddings_available():
        from .embedder import embed, serialize
        try:
            embedding_blob = serialize(embed(req.content))
        except Exception:
            # Embedding fallito — salva comunque senza embedding
            embedding_blob = None

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (agent_id, content, category, importance, embedding)
            VALUES (:agent_id, :content, :category, :importance, :embedding)
            """,
            {
                "agent_id": agent_id,
                "content": req.content,
                "category": req.category,
                "importance": importance,
                "embedding": embedding_blob,
            },
        )
        row_id = cursor.lastrowid

    # Invalida cache vettoriale per l'agente
    if embedding_blob:
        from .vector_index import get_index
        get_index().invalidate(agent_id)

    return row_id, importance


def search_memories(
    query: str,
    limit: int = 5,
    category: str | None = None,
    semantic: bool = True,
    agent_id: str = "default",
) -> list[MemoryRecord]:
    """
    Search memories. Uses semantic (embedding) search when available,
    falls back to FTS5 full-text search, then LIKE.
    Filters out fully-decayed memories. Reinforces access count on results.
    """
    if semantic and _embeddings_available():
        results = _semantic_search(query, limit * 2, category, agent_id)
    else:
        results = _fts_search(query, limit * 2, category, agent_id)

    # Filter forgotten memories, re-rank by effective score
    alive = [r for r in results if not should_forget(r.decay_score or 1.0)]
    alive.sort(key=lambda r: effective_score(r.decay_score or 1.0, r.importance), reverse=True)
    top = alive[:limit]

    # Reinforce access for retrieved memories
    if top:
        _reinforce([r.id for r in top])

    return top


def delete_memory(memory_id: int, agent_id: str = "default") -> bool:
    """Elimina una memoria per id, scoped per agente. Restituisce True se eliminata."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE id = ? AND agent_id = ?",
            (memory_id, agent_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        from .vector_index import get_index
        get_index().invalidate(agent_id)

    return deleted


def run_decay_pass(agent_id: str | None = None) -> int:
    """
    Recalculate decay_score for all active memories (optionally scoped to agent).
    Returns the count of memories updated. Thread-safe: un solo run alla volta.
    """
    if not _decay_lock.acquire(blocking=False):
        return 0  # run già in corso — skip silenzioso

    try:
        return _run_decay_pass_inner(agent_id)
    finally:
        _decay_lock.release()


def _run_decay_pass_inner(agent_id: str | None = None) -> int:
    with get_connection() as conn:
        sql = "SELECT id, importance, created_at, last_accessed, access_count FROM memories WHERE compressed_into IS NULL"
        params: list = []
        if agent_id:
            sql += " AND agent_id = ?"
            params.append(agent_id)
        rows = conn.execute(sql, params).fetchall()

    now = datetime.now(timezone.utc).isoformat()
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

    return len(updates)


def get_timeline(subject: str, limit: int = 20, agent_id: str = "default") -> list[MemoryRecord]:
    """Return memories about a subject ordered by creation time (oldest first)."""
    if _embeddings_available():
        results = _semantic_search(subject, limit, category=None, agent_id=agent_id)
    else:
        results = _fts_search(subject, limit, category=None, agent_id=agent_id)
    return sorted(results, key=lambda r: r.created_at)


# ── Private helpers ──────────────────────────────────────────────────────────

def _reinforce(memory_ids: list[int]) -> None:
    """Increment access_count and update last_accessed for retrieved memories."""
    now = datetime.now(timezone.utc).isoformat()
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


def _fts_search(query: str, limit: int, category: str | None, agent_id: str = "default") -> list[MemoryRecord]:
    """Full-text search via SQLite FTS5 with prefix wildcards, scoped to agent."""
    with get_connection() as conn:
        safe_query = _sanitize_fts_query(query)

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
                  {category_filter}
                ORDER BY rank, m.importance DESC
                LIMIT :limit
            """
            params: dict = {"query": safe_query, "limit": limit, "agent_id": agent_id}
        else:
            sql = """
                SELECT id, content, category, importance,
                       decay_score, access_count, last_accessed,
                       created_at, updated_at, NULL AS score
                FROM memories
                WHERE content LIKE :query
                  AND agent_id = :agent_id
                  AND compressed_into IS NULL
                  {category_filter}
                ORDER BY importance DESC, created_at DESC
                LIMIT :limit
            """
            params = {"query": f"%{query}%", "limit": limit, "agent_id": agent_id}

        category_filter = (
            "AND m.category = :category" if safe_query and category
            else "AND category = :category" if category
            else ""
        )
        if category:
            params["category"] = category

        rows = conn.execute(sql.format(category_filter=category_filter), params).fetchall()

    return [_row_to_record(r) for r in rows]


def _semantic_search(query: str, limit: int, category: str | None, agent_id: str = "default") -> list[MemoryRecord]:
    """Ricerca semantica con indice vettoriale in-memory, scoped per agente."""
    from .embedder import embed
    from .vector_index import get_index

    query_vec = embed(query)
    index = get_index()

    # Ricerca vettoriale batch via indice in-memory
    top_ids = index.search(query_vec, agent_id, category=category, limit=limit)
    if not top_ids:
        return []

    # Carica i record completi dal DB
    id_score_map = {mem_id: score for mem_id, score in top_ids}
    placeholders = ",".join("?" for _ in top_ids)

    with get_connection() as conn:
        sql = f"""
            SELECT id, content, category, importance,
                   decay_score, access_count, last_accessed,
                   created_at, updated_at
            FROM memories
            WHERE id IN ({placeholders})
        """
        params: list = [mem_id for mem_id, _ in top_ids]
        if category:
            sql = f"""
                SELECT id, content, category, importance,
                       decay_score, access_count, last_accessed,
                       created_at, updated_at
                FROM memories
                WHERE id IN ({placeholders}) AND category = ?
            """
            params.append(category)
        rows = conn.execute(sql, params).fetchall()

    results = []
    for row in rows:
        sim = id_score_map.get(row["id"], 0.0)
        results.append(MemoryRecord(
            id=row["id"],
            content=row["content"],
            category=row["category"],
            importance=row["importance"],
            decay_score=row["decay_score"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            score=round(sim, 4),
        ))

    # Ordina per score decrescente
    results.sort(key=lambda r: r.score or 0.0, reverse=True)
    return results


def _sanitize_fts_query(query: str) -> str:
    """Sanitizza query FTS5: rimuove operatori speciali, limita token."""
    special = set('"^():-*+<>&|')
    cleaned = "".join(c if c not in special else " " for c in query).strip()
    if not cleaned:
        return ""
    # Max 10 token, min 2 caratteri ciascuno — previene DoS
    tokens = [t for t in cleaned.split() if len(t) >= 2][:10]
    if not tokens:
        return ""
    # Quote per match esatto, wildcard suffix per flessibilita
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
