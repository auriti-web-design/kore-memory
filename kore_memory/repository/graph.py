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


def traverse_graph(
    start_id: int,
    agent_id: str = "default",
    depth: int = 3,
    relation_type: str | None = None,
) -> dict:
    """
    Multi-hop graph traversal using SQLite recursive CTE.
    Returns the start node and all reachable nodes within `depth` hops.
    """
    depth = min(depth, 10)  # cap to prevent excessive recursion

    relation_filter = ""

    with get_connection() as conn:
        # Verify start memory belongs to agent
        start = conn.execute(
            "SELECT id, content, category, importance, decay_score, created_at "
            "FROM memories WHERE id = ? AND agent_id = ? AND archived_at IS NULL",
            (start_id, agent_id),
        ).fetchone()
        if not start:
            return {"start": None, "nodes": [], "edges": [], "depth": depth}

        # Build CTE params: anchor(start_id), [relation_type], agent_id, depth, agent_id, start_id
        cte_params: list = [start_id]
        if relation_type:
            relation_filter = "AND r.relation = ?"
            cte_params.append(relation_type)
        cte_params.extend([agent_id, depth])
        # Outer query params
        outer_params = [agent_id, start_id]

        # Recursive CTE — traverse both directions
        rows = conn.execute(
            f"""
            WITH RECURSIVE graph_walk(node_id, hop) AS (
                -- Anchor: start node
                SELECT ? AS node_id, 0 AS hop
                UNION
                -- Recursive step: follow relations in both directions
                SELECT
                    CASE WHEN r.source_id = gw.node_id THEN r.target_id ELSE r.source_id END,
                    gw.hop + 1
                FROM graph_walk gw
                JOIN memory_relations r
                    ON (r.source_id = gw.node_id OR r.target_id = gw.node_id)
                    {relation_filter}
                JOIN memories m
                    ON m.id = CASE WHEN r.source_id = gw.node_id THEN r.target_id ELSE r.source_id END
                    AND m.agent_id = ?
                    AND m.archived_at IS NULL
                WHERE gw.hop < ?
            )
            SELECT DISTINCT gw.node_id, gw.hop,
                   m.content, m.category, m.importance, m.decay_score, m.created_at
            FROM graph_walk gw
            JOIN memories m ON m.id = gw.node_id AND m.agent_id = ?
            WHERE gw.node_id != ?
            ORDER BY gw.hop, m.importance DESC
            """,
            (*cte_params, *outer_params),
        ).fetchall()

        nodes = [
            {
                "id": r["node_id"],
                "content": r["content"],
                "category": r["category"],
                "importance": r["importance"],
                "decay_score": r["decay_score"],
                "created_at": r["created_at"],
                "hop": r["hop"],
            }
            for r in rows
        ]

        # Fetch edges between all discovered nodes
        node_ids = [start_id] + [n["id"] for n in nodes]
        if len(node_ids) > 1:
            placeholders = ",".join("?" * len(node_ids))
            edge_params: list = list(node_ids) + list(node_ids)
            if relation_type:
                edge_params.append(relation_type)
            edges_rows = conn.execute(
                f"""
                SELECT source_id, target_id, relation, created_at
                FROM memory_relations
                WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
                {"AND relation = ?" if relation_type else ""}
                """,
                edge_params,
            ).fetchall()
            edges = [dict(e) for e in edges_rows]
        else:
            edges = []

    return {
        "start": dict(start),
        "nodes": nodes,
        "edges": edges,
        "depth": depth,
    }
