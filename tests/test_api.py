"""
Kore — API tests
Fast, no-network, uses TestClient (ASGI in-process).
Auth: local-only mode enabled in tests (KORE_LOCAL_ONLY=1).
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use temp DB + local-only mode (no auth required)
os.environ["KORE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["KORE_LOCAL_ONLY"] = "1"

from src.main import app  # noqa: E402

# Default headers: agent namespace for isolation tests
HEADERS = {"X-Agent-Id": "test-agent"}
OTHER_AGENT = {"X-Agent-Id": "other-agent"}

client = TestClient(app)


class TestHealth:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert "semantic_search" in r.json()


class TestSave:
    def test_save_basic(self):
        r = client.post("/save", json={"content": "Juan works on Kore memory system", "category": "project"}, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert data["importance"] >= 1

    def test_save_auto_scores_credentials(self):
        r = client.post("/save", json={
            "content": "API token: sk-abc123 for production",
            "category": "general",
        }, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["importance"] == 5

    def test_save_rejects_blank(self):
        r = client.post("/save", json={"content": "   ", "category": "general"}, headers=HEADERS)
        assert r.status_code == 422

    def test_save_rejects_too_short(self):
        r = client.post("/save", json={"content": "hi", "category": "general"}, headers=HEADERS)
        assert r.status_code == 422


class TestAuth:
    def test_no_key_on_remote_fails(self):
        """When KORE_LOCAL_ONLY=0 and no key, should get 401."""
        os.environ["KORE_LOCAL_ONLY"] = "0"
        try:
            r = client.get("/search?q=test")
            assert r.status_code == 401
        finally:
            os.environ["KORE_LOCAL_ONLY"] = "1"

    def test_wrong_key_fails(self):
        os.environ["KORE_LOCAL_ONLY"] = "0"
        try:
            r = client.get("/search?q=test", headers={"X-Kore-Key": "wrong-key"})
            assert r.status_code == 403
        finally:
            os.environ["KORE_LOCAL_ONLY"] = "1"


class TestAgentIsolation:
    def setup_method(self):
        client.post("/save", json={"content": "Secret data for agent A only", "category": "general", "importance": 3}, headers=HEADERS)

    def test_other_agent_cannot_see_data(self):
        r = client.get("/search?q=Secret&semantic=false", headers=OTHER_AGENT)
        assert r.json()["total"] == 0

    def test_owner_agent_can_see_data(self):
        r = client.get("/search?q=Secret&semantic=false", headers=HEADERS)
        assert r.json()["total"] >= 1

    def test_other_agent_cannot_delete(self):
        save_r = client.post("/save", json={"content": "Memory to protect", "category": "general"}, headers=HEADERS)
        mid = save_r.json()["id"]
        del_r = client.delete(f"/memories/{mid}", headers=OTHER_AGENT)
        assert del_r.status_code == 404  # not found for other agent


class TestSearch:
    def setup_method(self):
        client.post("/save", json={"content": "CalcFast is a calculator website for Italian taxes", "category": "project", "importance": 3}, headers=HEADERS)
        client.post("/save", json={"content": "Betfair account has 40 euros for bot trading", "category": "finance", "importance": 4}, headers=HEADERS)

    def test_search_returns_results(self):
        r = client.get("/search?q=CalcFast&semantic=false", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_search_category_filter(self):
        r = client.get("/search?q=trading&category=finance&semantic=false", headers=HEADERS)
        assert r.status_code == 200
        for result in r.json()["results"]:
            assert result["category"] == "finance"


class TestDecay:
    def test_decay_run(self):
        r = client.post("/decay/run", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["updated"] >= 0


class TestCompress:
    def test_compress_run(self):
        r = client.post("/compress", headers=HEADERS)
        assert r.status_code == 200
        assert "clusters_found" in r.json()


class TestTimeline:
    def test_timeline(self):
        r = client.get("/timeline?subject=CalcFast", headers=HEADERS)
        assert r.status_code == 200
        results = r.json()["results"]
        if len(results) > 1:
            dates = [r["created_at"] for r in results]
            assert dates == sorted(dates)


class TestDelete:
    def test_delete_existing(self):
        save_r = client.post("/save", json={"content": "Temporary memory to delete", "category": "general"}, headers=HEADERS)
        mid = save_r.json()["id"]
        del_r = client.delete(f"/memories/{mid}", headers=HEADERS)
        assert del_r.status_code == 204

    def test_delete_nonexistent(self):
        r = client.delete("/memories/999999", headers=HEADERS)
        assert r.status_code == 404
