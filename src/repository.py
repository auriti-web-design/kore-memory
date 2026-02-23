"""
Kore — Repository layer
All database operations, keeping business logic out of routes.
"""

import threading
from datetime import datetime, timedelta, timezone

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

    # Calcola expires_at se TTL specificato
    expires_at = None
    if req.ttl_hours:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=req.ttl_hours)).isoformat()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (agent_id, content, category, importance, embedding, expires_at)
            VALUES (:agent_id, :content, :category, :importance, :embedding, :expires_at)
            """,
            {
                "agent_id": agent_id,
                "content": req.content,
                "category": req.category,
                "importance": importance,
                "embedding": embedding_blob,
                "expires_at": expires_at,
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
    cursor: tuple[float, int] | None = None,
) -> tuple[list[MemoryRecord], tuple[float, int] | None]:
    """
    Search memories with cursor-based pagination.
    
    Returns: (results, next_cursor)
    - results: list of MemoryRecord
    - next_cursor: (decay_score, id) for next page, or None if no more results
    
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

    # Filter forgotten memories, re-rank by effective score
    alive = [r for r in results if not should_forget(r.decay_score or 1.0)]
    alive.sort(key=lambda r: effective_score(r.decay_score or 1.0, r.importance), reverse=True)
    
    # Take requested page + 1 to check if there are more results
    page = alive[:limit + 1]
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

    return top, next_cursor


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


def cleanup_expired(agent_id: str | None = None) -> int:
    """Elimina memorie con TTL scaduto. Restituisce il numero di record rimossi."""
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
    Pulisce anche le memorie con TTL scaduto.
    Returns the count of memories updated. Thread-safe: un solo run alla volta.
    """
    if not _decay_lock.acquire(blocking=False):
        return 0  # run già in corso — skip silenzioso

    try:
        # Pulizia memorie scadute prima del ricalcolo
        cleanup_expired(agent_id)
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


def get_timeline(
    subject: str, 
    limit: int = 20, 
    agent_id: str = "default",
    cursor: tuple[float, int] | None = None,
) -> tuple[list[MemoryRecord], tuple[float, int] | None]:
    """Return memories about a subject ordered by creation time with cursor pagination."""
    fetch_limit = limit * 2  # Fetch extra for sorting
    
    if _embeddings_available():
        results = _semantic_search(subject, fetch_limit, category=None, agent_id=agent_id, cursor=cursor)
    else:
        results = _fts_search(subject, fetch_limit, category=None, agent_id=agent_id, cursor=cursor)
    
    # Sort by creation time (oldest first)
    sorted_results = sorted(results, key=lambda r: r.created_at)
    
    # Paginate
    page = sorted_results[:limit + 1]
    has_more = len(page) > limit
    top = page[:limit]
    
    next_cursor = None
    if has_more and top:
        last = top[-1]
        next_cursor = (last.decay_score or 1.0, last.id)
    
    return top, next_cursor


def export_memories(agent_id: str = "default") -> list[dict]:
    """Esporta tutte le memorie attive dell'agente come lista di dict (senza embedding)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, content, category, importance, decay_score,
                   access_count, last_accessed, created_at, updated_at
            FROM memories
            WHERE agent_id = ? AND compressed_into IS NULL
              AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC
            """,
            (agent_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def import_memories(records: list[dict], agent_id: str = "default") -> int:
    """Importa memorie da una lista di dict. Restituisce il numero di record importati."""
    imported = 0
    for rec in records:
        content = rec.get("content", "").strip()
        if not content or len(content) < 3:
            continue
        category = rec.get("category", "general")
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
    """Aggiunge tag a una memoria. Restituisce il numero di tag aggiunti."""
    # Verifica che la memoria appartenga all'agente
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
    """Rimuove tag da una memoria. Restituisce il numero di tag rimossi."""
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
    Restituisce i tag di una memoria.
    Verifica che la memoria appartenga all'agent_id specificato.
    """
    with get_connection() as conn:
        # JOIN con memories per verificare ownership
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
    """Cerca memorie per tag."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.content, m.category, m.importance,
                   m.decay_score, m.access_count, m.last_accessed,
                   m.created_at, m.updated_at, NULL AS score
            FROM memories m
            JOIN memory_tags t ON m.id = t.memory_id
            WHERE t.tag = ? AND m.agent_id = ? AND m.compressed_into IS NULL
              AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))
            ORDER BY m.importance DESC, m.created_at DESC
            LIMIT ?
            """,
            (tag.strip().lower(), agent_id, limit),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


# ── Relazioni ────────────────────────────────────────────────────────────────

def add_relation(
    source_id: int, target_id: int, relation: str = "related", agent_id: str = "default"
) -> bool:
    """Crea una relazione tra due memorie. Entrambe devono appartenere all'agente."""
    with get_connection() as conn:
        # Verifica che entrambe le memorie appartengano all'agente
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
    """Restituisce tutte le relazioni di una memoria (in entrambe le direzioni)."""
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
            cursor_filter = "AND ((m.decay_score, m.id) < (:cursor_score, :cursor_id))" if safe_query else \
                           "AND ((decay_score, id) < (:cursor_score, :cursor_id))"

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
                WHERE content LIKE :query
                  AND agent_id = :agent_id
                  AND compressed_into IS NULL
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
                  {category_filter}
                  {cursor_filter}
                ORDER BY decay_score DESC, id DESC
                LIMIT :limit
            """
            params = {"query": f"%{query}%", "limit": limit, "agent_id": agent_id}

        if cursor:
            params["cursor_score"] = cursor[0]
            params["cursor_id"] = cursor[1]

        category_filter = (
            "AND m.category = :category" if safe_query and category
            else "AND category = :category" if category
            else ""
        )
        if category:
            params["category"] = category

        rows = conn.execute(
            sql.format(category_filter=category_filter, cursor_filter=cursor_filter), 
            params
        ).fetchall()

    return [_row_to_record(r) for r in rows]


def _semantic_search(
    query: str, 
    limit: int, 
    category: str | None, 
    agent_id: str = "default",
    cursor: tuple[float, int] | None = None,
) -> list[MemoryRecord]:
    """Ricerca semantica con indice vettoriale in-memory, scoped per agente."""
    from .embedder import embed
    from .vector_index import get_index

    query_vec = embed(query)
    index = get_index()

    # Ricerca vettoriale batch via indice in-memory
    top_ids = index.search(query_vec, agent_id, category=category, limit=limit)
    if not top_ids:
        return []

    # Carica i record completi dal DB con cursor filter
    id_score_map = {mem_id: score for mem_id, score in top_ids}
    placeholders = ",".join("?" for _ in top_ids)

    cursor_filter = ""
    params = [id for id, _ in top_ids]
    
    if cursor:
        decay_score, last_id = cursor
        cursor_filter = "AND ((decay_score, id) < (?, ?))"
        params.extend([decay_score, last_id])

    with get_connection() as conn:
        sql = f"""
            SELECT id, content, category, importance,
                   decay_score, access_count, last_accessed,
                   created_at, updated_at
            FROM memories
            WHERE id IN ({placeholders})
              AND (expires_at IS NULL OR expires_at > datetime('now'))
              {cursor_filter}
            ORDER BY decay_score DESC, id DESC
        """
        params: list = [mem_id for mem_id, _ in top_ids]
        if category:
            sql = f"""
                SELECT id, content, category, importance,
                       decay_score, access_count, last_accessed,
                       created_at, updated_at
                FROM memories
                WHERE id IN ({placeholders}) AND category = ?
                  AND (expires_at IS NULL OR expires_at > datetime('now'))
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
