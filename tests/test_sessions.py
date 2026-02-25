"""
Tests for session/conversation tracking (v0.9.0).
"""

import os

import pytest

from fastapi.testclient import TestClient

from kore_memory.database import init_db, _pool
from kore_memory.main import app

HEADERS = {"X-Agent-Id": "test-agent"}


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    os.environ["KORE_DB_PATH"] = db_file
    _pool.clear()
    init_db()
    yield
    _pool.clear()


@pytest.fixture()
def client():
    return TestClient(app)


class TestSessionCreate:
    def test_create_session(self, client):
        r = client.post("/sessions", json={"session_id": "sess-001", "title": "Test Chat"}, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["id"] == "sess-001"
        assert data["agent_id"] == "test-agent"
        assert data["title"] == "Test Chat"

    def test_create_session_no_title(self, client):
        r = client.post("/sessions", json={"session_id": "sess-002"}, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["title"] is None

    def test_create_duplicate_session(self, client):
        client.post("/sessions", json={"session_id": "sess-dup"}, headers=HEADERS)
        r = client.post("/sessions", json={"session_id": "sess-dup"}, headers=HEADERS)
        assert r.status_code == 201  # INSERT OR IGNORE — idempotent


class TestSessionList:
    def test_list_empty(self, client):
        r = client.get("/sessions", headers=HEADERS)
        assert r.status_code == 200
        assert r.json() == []

    def test_list_sessions(self, client):
        client.post("/sessions", json={"session_id": "s1", "title": "Chat 1"}, headers=HEADERS)
        client.post("/sessions", json={"session_id": "s2", "title": "Chat 2"}, headers=HEADERS)
        r = client.get("/sessions", headers=HEADERS)
        data = r.json()
        assert len(data) == 2
        assert data[0]["id"] == "s2"  # newest first

    def test_sessions_scoped_to_agent(self, client):
        client.post("/sessions", json={"session_id": "s1"}, headers=HEADERS)
        client.post("/sessions", json={"session_id": "s2"}, headers={"X-Agent-Id": "other-agent"})
        r = client.get("/sessions", headers=HEADERS)
        assert len(r.json()) == 1


class TestSessionMemories:
    def test_save_with_session(self, client):
        """Save a memory with X-Session-Id header and retrieve session memories."""
        client.post("/sessions", json={"session_id": "chat-1"}, headers=HEADERS)
        # Save memories with session
        h = {**HEADERS, "X-Session-Id": "chat-1"}
        client.post("/save", json={"content": "First message in chat", "category": "general"}, headers=h)
        client.post("/save", json={"content": "Second message in chat", "category": "general"}, headers=h)
        # Save memory without session
        client.post("/save", json={"content": "Memory without session", "category": "general"}, headers=HEADERS)

        r = client.get("/sessions/chat-1/memories", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert "First message" in data["results"][0]["content"]

    def test_auto_create_session(self, client):
        """Session is auto-created when X-Session-Id is provided on save."""
        h = {**HEADERS, "X-Session-Id": "auto-sess"}
        client.post("/save", json={"content": "Auto session test memory", "category": "general"}, headers=h)

        r = client.get("/sessions", headers=HEADERS)
        sessions = r.json()
        assert any(s["id"] == "auto-sess" for s in sessions)

    def test_session_memories_empty(self, client):
        client.post("/sessions", json={"session_id": "empty-sess"}, headers=HEADERS)
        r = client.get("/sessions/empty-sess/memories", headers=HEADERS)
        assert r.json()["total"] == 0


class TestSessionSummary:
    def test_summary(self, client):
        h = {**HEADERS, "X-Session-Id": "sum-sess"}
        client.post("/save", json={"content": "Project discussion about API design", "category": "project", "importance": 4}, headers=h)
        client.post("/save", json={"content": "Decision to use REST over GraphQL", "category": "decision", "importance": 5}, headers=h)

        r = client.get("/sessions/sum-sess/summary", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == "sum-sess"
        assert data["memory_count"] == 2
        assert "project" in data["categories"]
        assert "decision" in data["categories"]
        assert data["avg_importance"] >= 4.0

    def test_summary_not_found(self, client):
        r = client.get("/sessions/nonexistent/summary", headers=HEADERS)
        assert r.status_code == 404


class TestSessionEnd:
    def test_end_session(self, client):
        client.post("/sessions", json={"session_id": "end-me"}, headers=HEADERS)
        r = client.post("/sessions/end-me/end", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["success"] is True

        # Verify session is ended
        sessions = client.get("/sessions", headers=HEADERS).json()
        ended = [s for s in sessions if s["id"] == "end-me"]
        assert ended[0]["ended_at"] is not None

    def test_end_already_ended(self, client):
        client.post("/sessions", json={"session_id": "end-twice"}, headers=HEADERS)
        client.post("/sessions/end-twice/end", headers=HEADERS)
        r = client.post("/sessions/end-twice/end", headers=HEADERS)
        assert r.status_code == 404

    def test_end_nonexistent(self, client):
        r = client.post("/sessions/nope/end", headers=HEADERS)
        assert r.status_code == 404


class TestSessionDelete:
    def test_delete_session(self, client):
        h = {**HEADERS, "X-Session-Id": "del-sess"}
        client.post("/save", json={"content": "Memory in session to delete", "category": "general"}, headers=h)

        r = client.delete("/sessions/del-sess", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["unlinked_memories"] == 1

        # Session gone
        sessions = client.get("/sessions", headers=HEADERS).json()
        assert not any(s["id"] == "del-sess" for s in sessions)

        # Memory still exists but unlinked
        r = client.get("/search?q=session+to+delete", headers=HEADERS)
        assert r.json()["total"] >= 1

    def test_delete_nonexistent(self, client):
        r = client.delete("/sessions/nope", headers=HEADERS)
        assert r.status_code == 200  # idempotent, just 0 unlinked


class TestSessionMemoryCount:
    def test_list_shows_memory_count(self, client):
        h = {**HEADERS, "X-Session-Id": "counted"}
        client.post("/save", json={"content": "Memory one in counted session", "category": "general"}, headers=h)
        client.post("/save", json={"content": "Memory two in counted session", "category": "general"}, headers=h)

        sessions = client.get("/sessions", headers=HEADERS).json()
        counted = [s for s in sessions if s["id"] == "counted"]
        assert counted[0]["memory_count"] == 2
