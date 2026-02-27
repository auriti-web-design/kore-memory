"""
Kore — Repository: Graph operations.
Tags and relations between memories.
"""

from __future__ import annotations

from ..database import get_connection


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
