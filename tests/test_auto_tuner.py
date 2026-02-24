"""
Kore — Auto-Tuner tests
Tests for the memory importance auto-tuning feature.
Uses TestClient (ASGI in-process, no network).
Auth: local-only mode enabled (KORE_LOCAL_ONLY=1).
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# DB temporaneo + local-only mode (no auth richiesta nei test)
os.environ["KORE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["KORE_LOCAL_ONLY"] = "1"

from kore_memory.database import get_connection, init_db  # noqa: E402
from kore_memory.main import app, _rate_buckets  # noqa: E402

# Inizializza schema
init_db()

HEADERS = {"X-Agent-Id": "test-agent"}
OTHER_AGENT = {"X-Agent-Id": "other-agent"}

client = TestClient(app)


def _clear_rate_limits():
    """Reset rate limiter to avoid 429 in tests."""
    _rate_buckets.clear()


def _insert_memory(
    agent_id: str = "test-agent",
    content: str = "Test memory for auto-tuner",
    category: str = "general",
    importance: int = 3,
    access_count: int = 0,
    age_days: int = 0,
) -> int:
    """Insert a memory directly into DB with full control over fields."""
    age_offset = f"-{age_days} days" if age_days > 0 else "+0 days"
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (agent_id, content, category, importance, access_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', ?), datetime('now'))
            """,
            (agent_id, content, category, importance, access_count, age_offset),
        )
        return cursor.lastrowid


class TestAutoTuneDisabled:
    """Test auto-tune when KORE_AUTO_TUNE is disabled (default)."""

    def setup_method(self):
        _clear_rate_limits()
        # Ensure auto-tune is disabled
        os.environ.pop("KORE_AUTO_TUNE", None)
        os.environ["KORE_AUTO_TUNE"] = "0"
        # Reload config to pick up the change
        from kore_memory import config
        config.AUTO_TUNE = os.getenv("KORE_AUTO_TUNE", "0") == "1"

    def test_auto_tune_disabled_returns_zero(self):
        """When disabled, auto-tune should return 0 boosted and 0 reduced."""
        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")
        assert result["boosted"] == 0
        assert result["reduced"] == 0
        assert "disabled" in result["message"].lower()

    def test_auto_tune_disabled_no_changes(self):
        """When disabled, no memories should be modified even if they qualify."""
        mid = _insert_memory(access_count=10, importance=2)
        from kore_memory.auto_tuner import run_auto_tune
        run_auto_tune(agent_id="test-agent")
        # Check that importance was NOT changed
        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 2

    def test_api_endpoint_when_disabled(self):
        """The /auto-tune endpoint should work but report disabled."""
        r = client.post("/auto-tune", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["boosted"] == 0
        assert data["reduced"] == 0


class TestAutoTuneBoost:
    """Test boosting of frequently accessed memories."""

    def setup_method(self):
        _clear_rate_limits()
        os.environ["KORE_AUTO_TUNE"] = "1"
        from kore_memory import config
        config.AUTO_TUNE = True

    def teardown_method(self):
        os.environ["KORE_AUTO_TUNE"] = "0"
        from kore_memory import config
        config.AUTO_TUNE = False

    def test_boost_high_access_count(self):
        """Memories with access_count >= 5 and importance < 5 should be boosted."""
        mid = _insert_memory(access_count=5, importance=3)
        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")
        assert result["boosted"] >= 1

        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 4  # 3 + 1

    def test_boost_does_not_exceed_5(self):
        """Importance should never be boosted above 5."""
        mid = _insert_memory(access_count=10, importance=5)
        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")
        # This memory should NOT be boosted (already at max)
        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 5

    def test_boost_threshold_boundary(self):
        """Memories with exactly access_count=4 should NOT be boosted."""
        mid = _insert_memory(access_count=4, importance=2)
        from kore_memory.auto_tuner import run_auto_tune
        run_auto_tune(agent_id="test-agent")
        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 2  # unchanged

    def test_boost_multiple_memories(self):
        """Multiple qualifying memories should all be boosted."""
        mid1 = _insert_memory(content="Boost me first", access_count=6, importance=1)
        mid2 = _insert_memory(content="Boost me second", access_count=8, importance=3)
        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")
        assert result["boosted"] >= 2

        with get_connection() as conn:
            r1 = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid1,)).fetchone()
            r2 = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid2,)).fetchone()
        assert r1["importance"] == 2  # 1 + 1
        assert r2["importance"] == 4  # 3 + 1


class TestAutoTuneReduce:
    """Test reduction of importance for never-accessed old memories."""

    def setup_method(self):
        _clear_rate_limits()
        os.environ["KORE_AUTO_TUNE"] = "1"
        from kore_memory import config
        config.AUTO_TUNE = True

    def teardown_method(self):
        os.environ["KORE_AUTO_TUNE"] = "0"
        from kore_memory import config
        config.AUTO_TUNE = False

    def test_reduce_old_never_accessed(self):
        """Memories never accessed and older than 30 days should be reduced."""
        mid = _insert_memory(access_count=0, importance=4, age_days=31)
        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")
        assert result["reduced"] >= 1

        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 3  # 4 - 1

    def test_reduce_does_not_go_below_1(self):
        """Importance should never be reduced below 1."""
        mid = _insert_memory(access_count=0, importance=1, age_days=60)
        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")
        # This memory should NOT be reduced (already at min)
        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 1

    def test_reduce_not_triggered_for_young_memories(self):
        """Memories younger than 30 days should NOT be reduced, even if never accessed."""
        mid = _insert_memory(access_count=0, importance=3, age_days=10)
        from kore_memory.auto_tuner import run_auto_tune
        run_auto_tune(agent_id="test-agent")
        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 3  # unchanged

    def test_reduce_not_triggered_if_accessed(self):
        """Old memories that HAVE been accessed should NOT be reduced."""
        mid = _insert_memory(access_count=1, importance=3, age_days=60)
        from kore_memory.auto_tuner import run_auto_tune
        run_auto_tune(agent_id="test-agent")
        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 3  # unchanged


class TestAutoTuneAgentIsolation:
    """Test that auto-tune respects agent isolation."""

    def setup_method(self):
        _clear_rate_limits()
        os.environ["KORE_AUTO_TUNE"] = "1"
        from kore_memory import config
        config.AUTO_TUNE = True

    def teardown_method(self):
        os.environ["KORE_AUTO_TUNE"] = "0"
        from kore_memory import config
        config.AUTO_TUNE = False

    def test_auto_tune_scoped_to_agent(self):
        """Auto-tune should only affect the specified agent's memories."""
        mid_own = _insert_memory(agent_id="test-agent", access_count=7, importance=2)
        mid_other = _insert_memory(agent_id="other-agent", access_count=7, importance=2)
        from kore_memory.auto_tuner import run_auto_tune
        run_auto_tune(agent_id="test-agent")
        with get_connection() as conn:
            own = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid_own,)).fetchone()
            other = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid_other,)).fetchone()
        assert own["importance"] == 3  # boosted
        assert other["importance"] == 2  # unchanged


class TestAutoTuneAPI:
    """Test the /auto-tune and /stats/scoring API endpoints."""

    def setup_method(self):
        _clear_rate_limits()

    def test_auto_tune_endpoint(self):
        """The /auto-tune endpoint returns the correct response structure."""
        r = client.post("/auto-tune", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "boosted" in data
        assert "reduced" in data
        assert "message" in data

    def test_auto_tune_endpoint_auth_required(self):
        """The /auto-tune endpoint requires auth when not in local-only mode."""
        os.environ["KORE_LOCAL_ONLY"] = "0"
        try:
            r = client.post("/auto-tune")
            assert r.status_code == 401
        finally:
            os.environ["KORE_LOCAL_ONLY"] = "1"

    def test_stats_scoring_endpoint(self):
        """The /stats/scoring endpoint returns the correct structure."""
        # Ensure at least one memory exists
        client.post("/save", json={"content": "Stats test memory content", "category": "general"}, headers=HEADERS)
        r = client.get("/stats/scoring", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "distribution" in data
        assert "avg_importance" in data
        assert "avg_access_count" in data
        assert "never_accessed_30d" in data
        assert "frequently_accessed" in data
        assert data["total"] >= 1

    def test_stats_scoring_distribution_keys(self):
        """Distribution should have keys for importance levels 1-5."""
        client.post("/save", json={"content": "Distribution test memory", "category": "general"}, headers=HEADERS)
        r = client.get("/stats/scoring", headers=HEADERS)
        dist = r.json()["distribution"]
        for level in ["1", "2", "3", "4", "5"]:
            assert level in dist

    def test_stats_scoring_empty_agent(self):
        """Stats for an agent with no memories should return zeroes."""
        r = client.get("/stats/scoring", headers={"X-Agent-Id": "empty-agent-xyz"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["avg_importance"] == 0.0
        assert data["avg_access_count"] == 0.0

    def test_stats_scoring_auth_required(self):
        """The /stats/scoring endpoint requires auth when not in local-only mode."""
        os.environ["KORE_LOCAL_ONLY"] = "0"
        try:
            r = client.get("/stats/scoring")
            assert r.status_code == 401
        finally:
            os.environ["KORE_LOCAL_ONLY"] = "1"


class TestAutoTuneIntegration:
    """Integration tests combining boost and reduce in a single run."""

    def setup_method(self):
        _clear_rate_limits()
        os.environ["KORE_AUTO_TUNE"] = "1"
        from kore_memory import config
        config.AUTO_TUNE = True

    def teardown_method(self):
        os.environ["KORE_AUTO_TUNE"] = "0"
        from kore_memory import config
        config.AUTO_TUNE = False

    def test_boost_and_reduce_in_same_run(self):
        """A single auto-tune run can both boost and reduce memories."""
        # Memory to boost: high access, low importance
        mid_boost = _insert_memory(content="Frequently accessed memory", access_count=10, importance=2)
        # Memory to reduce: never accessed, old, high importance
        mid_reduce = _insert_memory(content="Old forgotten memory", access_count=0, importance=4, age_days=45)

        from kore_memory.auto_tuner import run_auto_tune
        result = run_auto_tune(agent_id="test-agent")

        assert result["boosted"] >= 1
        assert result["reduced"] >= 1

        with get_connection() as conn:
            boosted = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid_boost,)).fetchone()
            reduced = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid_reduce,)).fetchone()

        assert boosted["importance"] == 3  # 2 + 1
        assert reduced["importance"] == 3  # 4 - 1

    def test_compressed_memories_not_affected(self):
        """Compressed memories should not be auto-tuned."""
        # Create a target memory (the "merged" record) and a memory to mark as compressed
        target_mid = _insert_memory(content="Merged target record")
        mid = _insert_memory(access_count=10, importance=2)
        with get_connection() as conn:
            conn.execute("UPDATE memories SET compressed_into = ? WHERE id = ?", (target_mid, mid))

        from kore_memory.auto_tuner import run_auto_tune
        run_auto_tune(agent_id="test-agent")

        with get_connection() as conn:
            row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mid,)).fetchone()
        assert row["importance"] == 2  # unchanged — compressed memories are skipped
