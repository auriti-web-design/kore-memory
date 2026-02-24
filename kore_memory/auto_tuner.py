"""
Kore — Memory Importance Auto-Tuner
Dynamically adjusts memory importance scores based on access patterns.

Rules:
  - Boost: memories accessed >= 5 times with importance < 5 get importance += 1
  - Reduce: memories never accessed (access_count == 0) older than 30 days
    with importance > 1 get importance -= 1

Controlled by KORE_AUTO_TUNE env var (disabled by default).
Thread-safe: only one auto-tune run at a time.
"""

import threading
from datetime import UTC, datetime

from . import config
from .database import get_connection
from .events import emit

# Event type for auto-tune operations
MEMORY_AUTO_TUNED = "memory.auto_tuned"

# Thresholds
BOOST_ACCESS_THRESHOLD = 5
REDUCE_AGE_DAYS = 30

# Thread-safe lock — prevents concurrent auto-tune runs
_auto_tune_lock = threading.Lock()


def run_auto_tune(agent_id: str | None = None) -> dict:
    """
    Run importance auto-tuning based on access patterns.

    - Boosts importance of frequently accessed memories (access_count >= 5, importance < 5)
    - Reduces importance of never-accessed memories older than 30 days (importance > 1)
    - Disabled by default; enable with KORE_AUTO_TUNE=1

    Returns {"boosted": N, "reduced": N, "message": "Auto-tune complete"}
    """
    if not config.AUTO_TUNE:
        return {"boosted": 0, "reduced": 0, "message": "Auto-tune is disabled"}

    if not _auto_tune_lock.acquire(blocking=False):
        return {"boosted": 0, "reduced": 0, "message": "Auto-tune already running"}

    try:
        return _run_auto_tune_inner(agent_id)
    finally:
        _auto_tune_lock.release()


def _run_auto_tune_inner(agent_id: str | None = None) -> dict:
    """Core auto-tune logic, runs inside the lock."""
    now_iso = datetime.now(UTC).isoformat()
    boosted = 0
    reduced = 0

    # ── Boost: frequently accessed memories ──────────────────────────────────
    with get_connection() as conn:
        sql = """
            SELECT id, importance, access_count
            FROM memories
            WHERE compressed_into IS NULL
              AND access_count >= :threshold
              AND importance < 5
        """
        params: dict = {"threshold": BOOST_ACCESS_THRESHOLD}
        if agent_id:
            sql += " AND agent_id = :agent_id"
            params["agent_id"] = agent_id

        rows = conn.execute(sql, params).fetchall()

        boost_updates = []
        for row in rows:
            new_importance = min(5, row["importance"] + 1)
            boost_updates.append((new_importance, now_iso, row["id"]))

        if boost_updates:
            conn.executemany(
                "UPDATE memories SET importance = ?, updated_at = ? WHERE id = ?",
                boost_updates,
            )
            boosted = len(boost_updates)

    # ── Reduce: never-accessed old memories ──────────────────────────────────
    with get_connection() as conn:
        sql = """
            SELECT id, importance
            FROM memories
            WHERE compressed_into IS NULL
              AND access_count = 0
              AND importance > 1
              AND created_at <= datetime('now', :age_offset)
        """
        params = {"age_offset": f"-{REDUCE_AGE_DAYS} days"}
        if agent_id:
            sql += " AND agent_id = :agent_id"
            params["agent_id"] = agent_id

        rows = conn.execute(sql, params).fetchall()

        reduce_updates = []
        for row in rows:
            new_importance = max(1, row["importance"] - 1)
            reduce_updates.append((new_importance, now_iso, row["id"]))

        if reduce_updates:
            conn.executemany(
                "UPDATE memories SET importance = ?, updated_at = ? WHERE id = ?",
                reduce_updates,
            )
            reduced = len(reduce_updates)

    if boosted > 0 or reduced > 0:
        emit(MEMORY_AUTO_TUNED, {
            "agent_id": agent_id,
            "boosted": boosted,
            "reduced": reduced,
        })

    return {"boosted": boosted, "reduced": reduced, "message": "Auto-tune complete"}


def get_scoring_stats(agent_id: str | None = None) -> dict:
    """
    Return statistics about the importance distribution of active memories.

    Returns:
        {
            "total": int,
            "distribution": {"1": N, "2": N, ...},
            "avg_importance": float,
            "avg_access_count": float,
            "never_accessed_30d": int,
            "frequently_accessed": int,
        }
    """
    with get_connection() as conn:
        # Base filter: active, non-compressed memories
        where = "WHERE compressed_into IS NULL"
        params: list = []
        if agent_id:
            where += " AND agent_id = ?"
            params.append(agent_id)

        # Total count
        total = conn.execute(
            f"SELECT COUNT(*) FROM memories {where}", params
        ).fetchone()[0]

        if total == 0:
            return {
                "total": 0,
                "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                "avg_importance": 0.0,
                "avg_access_count": 0.0,
                "never_accessed_30d": 0,
                "frequently_accessed": 0,
            }

        # Importance distribution
        dist_rows = conn.execute(
            f"SELECT importance, COUNT(*) as cnt FROM memories {where} GROUP BY importance",
            params,
        ).fetchall()
        distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for row in dist_rows:
            distribution[str(row["importance"])] = row["cnt"]

        # Averages
        avgs = conn.execute(
            f"SELECT AVG(importance) as avg_imp, AVG(access_count) as avg_acc FROM memories {where}",
            params,
        ).fetchone()
        avg_importance = round(avgs["avg_imp"] or 0.0, 2)
        avg_access_count = round(avgs["avg_acc"] or 0.0, 2)

        # Never accessed, older than 30 days
        never_sql = f"""
            SELECT COUNT(*) FROM memories
            {where}
              AND access_count = 0
              AND created_at <= datetime('now', '-30 days')
        """
        never_accessed_30d = conn.execute(never_sql, params).fetchone()[0]

        # Frequently accessed (access_count >= threshold)
        freq_sql = f"""
            SELECT COUNT(*) FROM memories
            {where}
              AND access_count >= ?
        """
        freq_params = params + [BOOST_ACCESS_THRESHOLD]
        frequently_accessed = conn.execute(freq_sql, freq_params).fetchone()[0]

    return {
        "total": total,
        "distribution": distribution,
        "avg_importance": avg_importance,
        "avg_access_count": avg_access_count,
        "never_accessed_30d": never_accessed_30d,
        "frequently_accessed": frequently_accessed,
    }
