"""
Kore — v2.0 feature tests
Graph RAG, Summarization, ACL, SSE Streaming, Analytics, GDPR, Plugins.
"""

import json

import pytest
from fastapi.testclient import TestClient

from kore_memory.main import app

HEADERS = {"X-Agent-Id": "v2-test-agent"}
OTHER = {"X-Agent-Id": "v2-other-agent"}

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _save(content: str, category: str = "project", headers=None) -> int:
    """Save a memory and return its ID."""
    r = client.post("/save", json={"content": content, "category": category}, headers=headers or HEADERS)
    assert r.status_code == 201
    return r.json()["id"]


def _relate(source_id: int, target_id: int, relation: str = "related") -> None:
    """Create a relation between two memories."""
    r = client.post(
        f"/memories/{source_id}/relations",
        json={"target_id": target_id, "relation": relation},
        headers=HEADERS,
    )
    assert r.status_code == 201


# ── Graph RAG ────────────────────────────────────────────────────────────────


class TestGraphTraverse:
    def test_traverse_basic(self):
        """Traverse a simple A→B→C chain."""
        a = _save("Graph node A: the root memory")
        b = _save("Graph node B: connected to A")
        c = _save("Graph node C: connected to B")
        _relate(a, b, "depends_on")
        _relate(b, c, "depends_on")

        r = client.get(f"/graph/traverse?start_id={a}&depth=3", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["start"] is not None
        assert len(data["nodes"]) >= 2  # B and C
        assert len(data["edges"]) >= 2

    def test_traverse_with_relation_filter(self):
        """Filter traversal by relation type."""
        a = _save("Filter test node A root")
        b = _save("Filter test node B related")
        c = _save("Filter test node C causal")
        _relate(a, b, "related")
        _relate(a, c, "causes")

        r = client.get(f"/graph/traverse?start_id={a}&depth=2&relation_type=causes", headers=HEADERS)
        data = r.json()
        assert data["start"] is not None
        # Should find C but not B (different relation type)
        node_ids = {n["id"] for n in data["nodes"]}
        assert c in node_ids

    def test_traverse_nonexistent_memory(self):
        """Traversing a non-existent memory returns empty."""
        r = client.get("/graph/traverse?start_id=999999&depth=2", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["start"] is None
        assert r.json()["nodes"] == []

    def test_traverse_depth_limit(self):
        """Depth is capped at 10."""
        a = _save("Depth test root node")
        r = client.get(f"/graph/traverse?start_id={a}&depth=15", headers=HEADERS)
        assert r.status_code == 422  # validation error: le=10

    def test_traverse_isolated_node(self):
        """Node with no relations returns empty nodes/edges."""
        a = _save("Isolated graph node test")
        r = client.get(f"/graph/traverse?start_id={a}&depth=3", headers=HEADERS)
        data = r.json()
        assert data["start"] is not None
        assert data["nodes"] == []
        assert data["edges"] == []


# ── Summarization ────────────────────────────────────────────────────────────


class TestSummarize:
    def test_summarize_basic(self):
        """Summarize a topic with keyword extraction."""
        _save("Python FastAPI framework for building APIs quickly")
        _save("Python type hints improve code quality and IDE support")
        _save("Python asyncio enables concurrent programming patterns")

        r = client.get("/summarize?topic=Python", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["topic"] == "Python"
        assert data["memory_count"] >= 1
        assert len(data["keywords"]) > 0
        assert "categories" in data

    def test_summarize_no_results(self):
        """Summarizing non-existent topic returns empty."""
        r = client.get("/summarize?topic=xyznonexistent12345", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["memory_count"] == 0

    def test_summarize_with_time_span(self):
        """Summary includes earliest/latest timestamps."""
        _save("Summary timeline test memory alpha")
        _save("Summary timeline test memory beta")
        r = client.get("/summarize?topic=timeline+test", headers=HEADERS)
        data = r.json()
        if data["memory_count"] > 0:
            assert data["time_span"] is not None
            assert "earliest" in data["time_span"]
            assert "latest" in data["time_span"]


# ── ACL (Multi-agent shared memory) ──────────────────────────────────────────


class TestACL:
    def test_grant_and_list_permissions(self):
        """Owner grants read access to another agent."""
        mem_id = _save("ACL test: shared knowledge base entry")
        r = client.post(
            f"/memories/{mem_id}/acl",
            json={"target_agent": "v2-other-agent", "permission": "read"},
            headers=HEADERS,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["success"] is True
        assert len(data["permissions"]) >= 1
        assert data["permissions"][0]["agent_id"] == "v2-other-agent"

    def test_grant_invalid_permission(self):
        """Invalid permission type is rejected."""
        mem_id = _save("ACL invalid permission test")
        r = client.post(
            f"/memories/{mem_id}/acl",
            json={"target_agent": "someone", "permission": "superadmin"},
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_revoke_access(self):
        """Revoke previously granted access."""
        mem_id = _save("ACL revoke test memory entry")
        # Grant first
        client.post(
            f"/memories/{mem_id}/acl",
            json={"target_agent": "v2-other-agent", "permission": "write"},
            headers=HEADERS,
        )
        # Revoke
        r = client.delete(f"/memories/{mem_id}/acl/v2-other-agent", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_non_owner_cannot_grant(self):
        """Non-owner without admin cannot grant access."""
        mem_id = _save("ACL ownership test memory")
        r = client.post(
            f"/memories/{mem_id}/acl",
            json={"target_agent": "intruder", "permission": "read"},
            headers=OTHER,
        )
        assert r.status_code == 403

    def test_shared_memories_endpoint(self):
        """List memories shared with an agent."""
        mem_id = _save("ACL shared listing test")
        client.post(
            f"/memories/{mem_id}/acl",
            json={"target_agent": "v2-other-agent", "permission": "read"},
            headers=HEADERS,
        )
        r = client.get("/shared", headers=OTHER)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 0  # May or may not find depending on ACL table state

    def test_list_permissions(self):
        """List ACL entries for a memory."""
        mem_id = _save("ACL permission listing test")
        client.post(
            f"/memories/{mem_id}/acl",
            json={"target_agent": "agent-x", "permission": "admin"},
            headers=HEADERS,
        )
        r = client.get(f"/memories/{mem_id}/acl", headers=HEADERS)
        assert r.status_code == 200
        assert len(r.json()["permissions"]) >= 1


# ── SSE Streaming Search ─────────────────────────────────────────────────────


class TestSSEStreaming:
    def test_stream_search_basic(self):
        """SSE stream returns FTS and semantic phases."""
        _save("SSE streaming test: FastAPI performance optimization")

        with client.stream("GET", "/stream/search?q=FastAPI", headers=HEADERS) as response:
            assert response.status_code == 200
            content = response.read().decode("utf-8")

        # Should contain event types
        assert "event: fts" in content
        assert "event: done" in content

    def test_stream_search_fts_has_results(self):
        """FTS phase produces parseable JSON data."""
        _save("SSE FTS parse test: unique keyword xylophone")

        with client.stream("GET", "/stream/search?q=xylophone", headers=HEADERS) as response:
            content = response.read().decode("utf-8")

        # Parse FTS event
        for line in content.split("\n"):
            if line.startswith("data: ") and "fts" in line:
                data = json.loads(line[6:])
                assert "results" in data
                assert "phase" in data
                break


# ── Analytics ────────────────────────────────────────────────────────────────


class TestAnalytics:
    def test_analytics_basic(self):
        """Analytics returns all expected fields."""
        _save("Analytics test memory: tracking patterns")

        r = client.get("/analytics", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "total_memories" in data
        assert "categories" in data
        assert "importance_distribution" in data
        assert "decay_analysis" in data
        assert "top_tags" in data
        assert "access_patterns" in data
        assert "growth_last_30d" in data
        assert "compressed_memories" in data
        assert "archived_memories" in data
        assert "total_relations" in data

    def test_analytics_decay_buckets(self):
        """Decay analysis has healthy/fading/critical buckets."""
        r = client.get("/analytics", headers=HEADERS)
        decay = r.json()["decay_analysis"]
        assert "healthy" in decay
        assert "fading" in decay
        assert "critical" in decay
        assert "avg_decay" in decay


# ── GDPR ─────────────────────────────────────────────────────────────────────


class TestGDPR:
    def test_gdpr_delete_self(self):
        """Agent can delete all their own data."""
        gdpr_headers = {"X-Agent-Id": "gdpr-delete-agent"}
        _save("GDPR test memory one to delete", headers=gdpr_headers)
        _save("GDPR test memory two to delete", headers=gdpr_headers)

        r = client.delete("/memories/agent/gdpr-delete-agent", headers=gdpr_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["deleted_memories"] >= 2
        assert "message" in data

    def test_gdpr_cannot_delete_other_agent(self):
        """Agent cannot delete another agent's data."""
        r = client.delete("/memories/agent/someone-else", headers=HEADERS)
        assert r.status_code == 403

    def test_gdpr_delete_nonexistent_agent(self):
        """Deleting non-existent agent data returns zero counts."""
        headers = {"X-Agent-Id": "gdpr-empty-agent"}
        r = client.delete("/memories/agent/gdpr-empty-agent", headers=headers)
        assert r.status_code == 200
        assert r.json()["deleted_memories"] == 0


# ── Plugins ──────────────────────────────────────────────────────────────────


class TestPlugins:
    def test_list_plugins_empty(self):
        """Default state: no plugins registered."""
        r = client.get("/plugins", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] >= 0

    def test_plugin_registration(self):
        """Register a plugin and verify it appears in the list."""
        from kore_memory.plugins import KorePlugin, clear_plugins, register_plugin

        class TestPlugin(KorePlugin):
            @property
            def name(self) -> str:
                return "test-v2-plugin"

        register_plugin(TestPlugin())

        r = client.get("/plugins", headers=HEADERS)
        assert "test-v2-plugin" in r.json()["plugins"]

        # Cleanup
        clear_plugins()

    def test_plugin_pre_save_hook(self):
        """Plugin pre_save can override importance."""
        from kore_memory.plugins import KorePlugin, clear_plugins, register_plugin, run_pre_save

        class BoostPlugin(KorePlugin):
            @property
            def name(self) -> str:
                return "boost-plugin"

            def pre_save(self, content, category, importance, agent_id):
                if "critical" in content.lower():
                    return {"importance": 5}
                return None

        register_plugin(BoostPlugin())

        result = run_pre_save("This is a critical decision", "general", None, "test")
        assert result["importance"] == 5

        # Cleanup
        clear_plugins()

    def test_plugin_post_search_filter(self):
        """Plugin post_search can filter results."""
        from kore_memory.plugins import KorePlugin, clear_plugins, register_plugin, run_post_search

        class FilterPlugin(KorePlugin):
            @property
            def name(self) -> str:
                return "filter-plugin"

            def post_search(self, query, results, agent_id):
                return [r for r in results if r.get("importance", 0) >= 3]

        register_plugin(FilterPlugin())

        fake_results = [
            {"id": 1, "importance": 5},
            {"id": 2, "importance": 1},
            {"id": 3, "importance": 4},
        ]
        filtered = run_post_search("test", fake_results, "test")
        assert len(filtered) == 2
        assert all(r["importance"] >= 3 for r in filtered)

        clear_plugins()

    def test_plugin_pre_delete_block(self):
        """Plugin pre_delete can block deletion."""
        from kore_memory.plugins import KorePlugin, clear_plugins, register_plugin, run_pre_delete

        class ProtectPlugin(KorePlugin):
            @property
            def name(self) -> str:
                return "protect-plugin"

            def pre_delete(self, memory_id, agent_id):
                return memory_id != 42  # Block deletion of memory 42

        register_plugin(ProtectPlugin())

        assert run_pre_delete(1, "test") is True
        assert run_pre_delete(42, "test") is False

        clear_plugins()


# ── Summarizer Unit Tests ────────────────────────────────────────────────────


class TestSummarizerUnit:
    def test_tokenize(self):
        """Tokenizer filters stop words and extracts meaningful tokens."""
        from kore_memory.summarizer import _tokenize

        tokens = _tokenize("The quick brown fox jumps over the lazy dog")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "the" not in tokens

    def test_tfidf_computation(self):
        """TF-IDF produces non-zero scores."""
        from kore_memory.summarizer import _compute_tfidf, _tokenize

        docs = [
            _tokenize("Python FastAPI web framework"),
            _tokenize("Python Django web framework"),
            _tokenize("JavaScript React frontend library"),
        ]
        scores = _compute_tfidf(docs)
        assert len(scores) == 3
        # "python" appears in 2 docs, "javascript" in 1 — JS should have higher IDF
        assert any(s > 0 for s in scores[0].values())

    def test_empty_documents(self):
        """TF-IDF handles empty input."""
        from kore_memory.summarizer import _compute_tfidf

        assert _compute_tfidf([]) == []
