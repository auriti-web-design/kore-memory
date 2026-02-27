"""
Kore — Analytics
Aggregated statistics: category distribution, decay analysis, top tags,
access patterns, memory growth over time.
"""

from __future__ import annotations

from .database import get_connection


def get_analytics(agent_id: str = "default") -> dict:
    """Compute comprehensive analytics for an agent's memory store."""
    with get_connection() as conn:
        # Total memories
        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND compressed_into IS NULL AND archived_at IS NULL",
            (agent_id,),
        ).fetchone()[0]

        # Category distribution
        cat_rows = conn.execute(
            """SELECT category, COUNT(*) AS cnt
               FROM memories
               WHERE agent_id = ? AND compressed_into IS NULL AND archived_at IS NULL
               GROUP BY category ORDER BY cnt DESC""",
            (agent_id,),
        ).fetchall()
        categories = {r["category"]: r["cnt"] for r in cat_rows}

        # Importance distribution
        imp_rows = conn.execute(
            """SELECT importance, COUNT(*) AS cnt
               FROM memories
               WHERE agent_id = ? AND compressed_into IS NULL AND archived_at IS NULL
               GROUP BY importance ORDER BY importance""",
            (agent_id,),
        ).fetchall()
        importance_dist = {str(r["importance"]): r["cnt"] for r in imp_rows}

        # Decay distribution (buckets: healthy >0.7, fading 0.3-0.7, critical <0.3)
        decay_rows = conn.execute(
            """SELECT
                SUM(CASE WHEN decay_score > 0.7 THEN 1 ELSE 0 END) AS healthy,
                SUM(CASE WHEN decay_score BETWEEN 0.3 AND 0.7 THEN 1 ELSE 0 END) AS fading,
                SUM(CASE WHEN decay_score < 0.3 THEN 1 ELSE 0 END) AS critical,
                ROUND(AVG(decay_score), 3) AS avg_decay
               FROM memories
               WHERE agent_id = ? AND compressed_into IS NULL AND archived_at IS NULL""",
            (agent_id,),
        ).fetchone()
        decay_analysis = {
            "healthy": decay_rows["healthy"] or 0,
            "fading": decay_rows["fading"] or 0,
            "critical": decay_rows["critical"] or 0,
            "avg_decay": decay_rows["avg_decay"] or 0.0,
        }

        # Top tags
        tag_rows = conn.execute(
            """SELECT mt.tag, COUNT(*) AS cnt
               FROM memory_tags mt
               JOIN memories m ON m.id = mt.memory_id
               WHERE m.agent_id = ? AND m.archived_at IS NULL AND m.compressed_into IS NULL
               GROUP BY mt.tag ORDER BY cnt DESC LIMIT 20""",
            (agent_id,),
        ).fetchall()
        top_tags = [{"tag": r["tag"], "count": r["cnt"]} for r in tag_rows]

        # Access patterns
        access_rows = conn.execute(
            """SELECT
                SUM(CASE WHEN access_count = 0 THEN 1 ELSE 0 END) AS never_accessed,
                SUM(CASE WHEN access_count BETWEEN 1 AND 5 THEN 1 ELSE 0 END) AS low_access,
                SUM(CASE WHEN access_count BETWEEN 6 AND 20 THEN 1 ELSE 0 END) AS medium_access,
                SUM(CASE WHEN access_count > 20 THEN 1 ELSE 0 END) AS high_access,
                ROUND(AVG(access_count), 1) AS avg_access
               FROM memories
               WHERE agent_id = ? AND compressed_into IS NULL AND archived_at IS NULL""",
            (agent_id,),
        ).fetchone()
        access_patterns = {
            "never_accessed": access_rows["never_accessed"] or 0,
            "low_access": access_rows["low_access"] or 0,
            "medium_access": access_rows["medium_access"] or 0,
            "high_access": access_rows["high_access"] or 0,
            "avg_access": access_rows["avg_access"] or 0.0,
        }

        # Memory growth over time (last 30 days, grouped by day)
        growth_rows = conn.execute(
            """SELECT DATE(created_at) AS day, COUNT(*) AS cnt
               FROM memories
               WHERE agent_id = ? AND created_at >= datetime('now', '-30 days')
                 AND compressed_into IS NULL
               GROUP BY DATE(created_at) ORDER BY day""",
            (agent_id,),
        ).fetchall()
        growth = [{"date": r["day"], "count": r["cnt"]} for r in growth_rows]

        # Compression stats
        compressed = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND compressed_into IS NOT NULL",
            (agent_id,),
        ).fetchone()[0]

        archived = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE agent_id = ? AND archived_at IS NOT NULL",
            (agent_id,),
        ).fetchone()[0]

        # Relations count
        relations = conn.execute(
            """SELECT COUNT(*) FROM memory_relations r
               JOIN memories m ON m.id = r.source_id
               WHERE m.agent_id = ?""",
            (agent_id,),
        ).fetchone()[0]

    return {
        "total_memories": total,
        "categories": categories,
        "importance_distribution": importance_dist,
        "decay_analysis": decay_analysis,
        "top_tags": top_tags,
        "access_patterns": access_patterns,
        "growth_last_30d": growth,
        "compressed_memories": compressed,
        "archived_memories": archived,
        "total_relations": relations,
    }
