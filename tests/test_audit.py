"""
Kore — Audit log tests
Tests for event audit logging, querying, cleanup, and the /audit endpoint.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# DB temporaneo + local-only mode (no auth richiesta nei test)
os.environ["KORE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["KORE_LOCAL_ONLY"] = "1"

from kore_memory import events  # noqa: E402
from kore_memory.audit import (  # noqa: E402
    _audit_handler,
    cleanup_audit_log,
    query_audit_log,
    register_audit_handler,
)
from kore_memory.database import get_connection, init_db  # noqa: E402
from kore_memory.main import app  # noqa: E402

init_db()

HEADERS = {"X-Agent-Id": "test-agent"}
OTHER_AGENT = {"X-Agent-Id": "other-agent"}

client = TestClient(app)


class TestAuditDisabled:
    """When audit is not explicitly enabled, no entries should be saved."""

    def test_no_entries_without_registration(self):
        """Events emitted without a registered audit handler produce no log rows."""
        # Clear any previously registered handlers
        events.clear()
        client.post(
            "/save",
            json={"content": "This should not be audited", "category": "general"},
            headers=HEADERS,
        )
        entries = query_audit_log("test-agent")
        # No audit handler registered, so nothing should be logged
        assert len(entries) == 0


class TestAuditEnabled:
    """Tests with the audit handler registered."""

    @classmethod
    def setup_class(cls):
        events.clear()
        register_audit_handler()

    @classmethod
    def teardown_class(cls):
        events.clear()

    def test_save_event_captured(self):
        """Saving a memory should produce a memory.saved audit entry."""
        r = client.post(
            "/save",
            json={"content": "Audit test: memory save event", "category": "project"},
            headers=HEADERS,
        )
        assert r.status_code == 201
        memory_id = r.json()["id"]

        entries = query_audit_log("test-agent", event_type="memory.saved")
        matching = [e for e in entries if e["memory_id"] == memory_id]
        assert len(matching) >= 1
        assert matching[0]["event"] == "memory.saved"
        assert matching[0]["agent_id"] == "test-agent"
        assert matching[0]["data"]["id"] == memory_id

    def test_delete_event_captured(self):
        """Deleting a memory should produce a memory.deleted audit entry."""
        r = client.post(
            "/save",
            json={"content": "Audit test: to be deleted", "category": "general"},
            headers=HEADERS,
        )
        memory_id = r.json()["id"]

        client.delete(f"/memories/{memory_id}", headers=HEADERS)

        entries = query_audit_log("test-agent", event_type="memory.deleted")
        matching = [e for e in entries if e["memory_id"] == memory_id]
        assert len(matching) >= 1
        assert matching[0]["event"] == "memory.deleted"

    def test_update_event_captured(self):
        """Updating a memory should produce a memory.updated audit entry."""
        r = client.post(
            "/save",
            json={"content": "Audit test: to be updated", "category": "general"},
            headers=HEADERS,
        )
        memory_id = r.json()["id"]

        client.put(
            f"/memories/{memory_id}",
            json={"content": "Audit test: updated content"},
            headers=HEADERS,
        )

        entries = query_audit_log("test-agent", event_type="memory.updated")
        matching = [e for e in entries if e["memory_id"] == memory_id]
        assert len(matching) >= 1
        assert matching[0]["event"] == "memory.updated"

    def test_query_event_type_filter(self):
        """Querying with event_type filter returns only matching events."""
        # Create at least one save and one delete
        r = client.post(
            "/save",
            json={"content": "Audit filter test memory", "category": "general"},
            headers=HEADERS,
        )
        mid = r.json()["id"]
        client.delete(f"/memories/{mid}", headers=HEADERS)

        saved = query_audit_log("test-agent", event_type="memory.saved")
        deleted = query_audit_log("test-agent", event_type="memory.deleted")

        assert all(e["event"] == "memory.saved" for e in saved)
        assert all(e["event"] == "memory.deleted" for e in deleted)

    def test_query_since_filter(self):
        """Querying with since filter returns only events after the timestamp."""
        # All test events were created 'now', querying since far future should return nothing
        entries = query_audit_log("test-agent", since="2099-01-01T00:00:00")
        assert len(entries) == 0

        # Querying since far past should return events
        entries = query_audit_log("test-agent", since="2000-01-01T00:00:00")
        assert len(entries) > 0

    def test_query_limit(self):
        """Querying with a limit caps the number of results."""
        entries = query_audit_log("test-agent", limit=2)
        assert len(entries) <= 2

    def test_cleanup_old_entries(self):
        """Cleanup removes entries older than specified days."""
        # Insert an old entry directly
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO event_logs (event, agent_id, memory_id, data, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now', '-100 days'))",
                ("memory.saved", "test-agent", 999, '{"id": 999, "agent_id": "test-agent"}'),
            )

        # Verify it exists
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM event_logs WHERE memory_id = 999"
            ).fetchone()
            assert row["cnt"] == 1

        # Cleanup entries older than 90 days
        removed = cleanup_audit_log(days=90)
        assert removed >= 1

        # Verify old entry is gone
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM event_logs WHERE memory_id = 999"
            ).fetchone()
            assert row["cnt"] == 0

    def test_cleanup_preserves_recent(self):
        """Cleanup does not remove recent entries."""
        before = query_audit_log("test-agent")
        recent_count = len(before)

        removed = cleanup_audit_log(days=90)

        after = query_audit_log("test-agent")
        # All recent entries should still be there
        assert len(after) == recent_count

    def test_agent_isolation(self):
        """Audit entries are scoped to their agent_id."""
        # Save with other-agent
        r = client.post(
            "/save",
            json={"content": "Audit isolation test from other agent", "category": "general"},
            headers=OTHER_AGENT,
        )
        other_id = r.json()["id"]

        # Query as test-agent should not see other-agent's events
        entries = query_audit_log("test-agent")
        other_entries = [e for e in entries if e["memory_id"] == other_id]
        assert len(other_entries) == 0

        # Query as other-agent should see the event
        entries = query_audit_log("other-agent", event_type="memory.saved")
        other_entries = [e for e in entries if e["memory_id"] == other_id]
        assert len(other_entries) >= 1


class TestAuditEndpoint:
    """Tests for the /audit REST endpoint."""

    @classmethod
    def setup_class(cls):
        events.clear()
        register_audit_handler()

    @classmethod
    def teardown_class(cls):
        events.clear()

    def test_endpoint_returns_events(self):
        """GET /audit returns audit events for the agent."""
        # Save something to generate an event
        client.post(
            "/save",
            json={"content": "Endpoint test memory", "category": "general"},
            headers=HEADERS,
        )

        r = client.get("/audit", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_endpoint_event_filter(self):
        """GET /audit?event=memory.saved filters by event type."""
        r = client.get("/audit?event=memory.saved", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert all(e["event"] == "memory.saved" for e in data["events"])

    def test_endpoint_limit(self):
        """GET /audit?limit=1 respects limit."""
        r = client.get("/audit?limit=1", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert len(data["events"]) <= 1
        assert data["total"] <= 1

    def test_endpoint_since_filter(self):
        """GET /audit?since=... filters by timestamp."""
        r = client.get("/audit?since=2099-01-01T00:00:00", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_endpoint_agent_isolation(self):
        """GET /audit only returns events for the requesting agent."""
        r_test = client.get("/audit", headers=HEADERS)
        r_other = client.get("/audit", headers=OTHER_AGENT)
        assert r_test.status_code == 200
        assert r_other.status_code == 200

        # test-agent events should not appear in other-agent results
        test_ids = {e["id"] for e in r_test.json()["events"]}
        other_ids = {e["id"] for e in r_other.json()["events"]}
        assert test_ids.isdisjoint(other_ids)


class TestAuditHandlerDirect:
    """Direct unit tests for the audit handler function."""

    def test_handler_signature(self):
        """The handler accepts (event, data) as expected by the events system."""
        _audit_handler("memory.saved", {"id": 9999, "agent_id": "direct-test"})

        entries = query_audit_log("direct-test", event_type="memory.saved")
        matching = [e for e in entries if e["memory_id"] == 9999]
        assert len(matching) >= 1
        assert matching[0]["data"]["id"] == 9999

    def test_handler_with_empty_data(self):
        """The handler handles empty data gracefully."""
        _audit_handler("memory.decayed", {})

        entries = query_audit_log("default", event_type="memory.decayed")
        assert len(entries) >= 1
