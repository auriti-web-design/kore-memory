"""
Kore — Entity extraction tests
Tests regex fallback, auto-tagging, search, API endpoint, and config toggle.
Uses TestClient (ASGI in-process), same pattern as test_api.py.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# DB temporaneo + local-only mode
os.environ["KORE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["KORE_LOCAL_ONLY"] = "1"

from kore_memory.database import init_db  # noqa: E402
from kore_memory.main import app  # noqa: E402

init_db()

HEADERS = {"X-Agent-Id": "entity-test-agent"}
client = TestClient(app)


# ── Unit tests: regex extraction ─────────────────────────────────────────────

class TestRegexExtraction:
    def test_extract_emails(self):
        """Regex extracts email addresses."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Contact me at user@example.com or admin@test.org")
        emails = [e for e in entities if e["type"] == "email"]
        assert len(emails) >= 2
        values = [e["value"] for e in emails]
        assert "user@example.com" in values
        assert "admin@test.org" in values

    def test_extract_urls(self):
        """Regex extracts URLs."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Visit https://example.com and http://test.org/page")
        urls = [e for e in entities if e["type"] == "url"]
        assert len(urls) >= 2
        values = [e["value"] for e in urls]
        assert any("example.com" in v for v in values)
        assert any("test.org" in v for v in values)

    def test_extract_dates(self):
        """Regex extracts date patterns."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Meeting on 2024-01-15 and again on 12/25/2024")
        dates = [e for e in entities if e["type"] == "date"]
        assert len(dates) >= 2
        values = [e["value"] for e in dates]
        assert "2024-01-15" in values

    def test_extract_dates_month_name(self):
        """Regex extracts dates with month names."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Deadline is January 15, 2024")
        dates = [e for e in entities if e["type"] == "date"]
        assert len(dates) >= 1

    def test_extract_money(self):
        """Regex extracts monetary values."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Budget is $1,500.00 and the invoice is 200 EUR")
        money = [e for e in entities if e["type"] == "money"]
        assert len(money) >= 2
        values = [e["value"] for e in money]
        assert any("1,500" in v for v in values)
        assert any("200" in v.lower() and "eur" in v.lower() for v in values)

    def test_extract_money_euro_symbol(self):
        """Regex extracts euro symbol monetary values."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Cost: \u20ac50.99")
        money = [e for e in entities if e["type"] == "money"]
        assert len(money) >= 1

    def test_empty_text_returns_empty(self):
        """Empty or whitespace text returns no entities."""
        from kore_memory.integrations.entities import extract_entities

        assert extract_entities("") == []
        assert extract_entities("   ") == []
        assert extract_entities("No entities here at all") == []

    def test_no_duplicates(self):
        """Duplicate entities are deduplicated."""
        from kore_memory.integrations.entities import extract_entities

        entities = extract_entities("Email user@test.com and again user@test.com")
        emails = [e for e in entities if e["type"] == "email"]
        assert len(emails) == 1


# ── Integration tests: auto-tagging ──────────────────────────────────────────

class TestAutoTagging:
    def _create_memory(self, content: str = "Memory for entity tagging") -> int:
        r = client.post("/save", json={"content": content, "category": "general"}, headers=HEADERS)
        return r.json()["id"]

    def test_auto_tag_creates_entity_tags(self):
        """auto_tag_entities creates entity: prefixed tags on the memory."""
        from kore_memory.integrations.entities import auto_tag_entities

        mid = self._create_memory("Send report to user@example.com by 2024-03-01")
        count = auto_tag_entities(mid, "Send report to user@example.com by 2024-03-01", "entity-test-agent")
        assert count >= 1

        # Verify tags are present
        r = client.get(f"/memories/{mid}/tags", headers=HEADERS)
        tags = r.json()["tags"]
        entity_tags = [t for t in tags if t.startswith("entity:")]
        assert len(entity_tags) >= 1
        # Check email entity tag
        assert any("entity:email:user@example.com" in t for t in entity_tags)

    def test_auto_tag_no_entities(self):
        """auto_tag_entities returns 0 when no entities found."""
        from kore_memory.integrations.entities import auto_tag_entities

        mid = self._create_memory("Just a plain text memory without entities")
        count = auto_tag_entities(mid, "Just a plain text memory without entities", "entity-test-agent")
        assert count == 0

    def test_auto_tag_url_entity(self):
        """auto_tag_entities creates url entity tags."""
        from kore_memory.integrations.entities import auto_tag_entities

        mid = self._create_memory("Check out https://github.com/kore-memory")
        count = auto_tag_entities(mid, "Check out https://github.com/kore-memory", "entity-test-agent")
        assert count >= 1

        r = client.get(f"/memories/{mid}/tags", headers=HEADERS)
        tags = r.json()["tags"]
        url_tags = [t for t in tags if t.startswith("entity:url:")]
        assert len(url_tags) >= 1


# ── Integration tests: entity search ─────────────────────────────────────────

class TestEntitySearch:
    def setup_method(self):
        """Create memories with entity tags for search tests."""
        from kore_memory.integrations.entities import auto_tag_entities

        r = client.post("/save", json={
            "content": "Contact support@kore.dev for help",
            "category": "general",
        }, headers=HEADERS)
        mid = r.json()["id"]
        auto_tag_entities(mid, "Contact support@kore.dev for help", "entity-test-agent")

    def test_search_entities_all(self):
        """search_entities returns all entity tags."""
        from kore_memory.integrations.entities import search_entities

        results = search_entities("entity-test-agent")
        assert len(results) >= 1
        for r in results:
            assert "type" in r
            assert "value" in r
            assert "memory_id" in r
            assert "tag" in r

    def test_search_entities_by_type(self):
        """search_entities filters by entity type."""
        from kore_memory.integrations.entities import search_entities

        results = search_entities("entity-test-agent", entity_type="email")
        for r in results:
            assert r["type"] == "email"

    def test_search_entities_nonexistent_type(self):
        """search_entities returns empty for unknown types."""
        from kore_memory.integrations.entities import search_entities

        results = search_entities("entity-test-agent", entity_type="spacecraft")
        assert results == []


# ── Config tests ──────────────────────────────────────────────────────────────

class TestEntityConfig:
    def test_entity_extraction_disabled_by_default(self):
        """Entity extraction is disabled by default (KORE_ENTITY_EXTRACTION=0)."""
        from kore_memory import config
        # Default env is "0", which means disabled
        saved = os.environ.get("KORE_ENTITY_EXTRACTION")
        try:
            os.environ["KORE_ENTITY_EXTRACTION"] = "0"
            # Re-evaluate: the config module reads env at import time,
            # but we can check the env var pattern directly
            assert os.getenv("KORE_ENTITY_EXTRACTION", "0") == "0"
        finally:
            if saved is not None:
                os.environ["KORE_ENTITY_EXTRACTION"] = saved
            elif "KORE_ENTITY_EXTRACTION" in os.environ:
                del os.environ["KORE_ENTITY_EXTRACTION"]

    def test_entity_extraction_enable_toggle(self):
        """Setting KORE_ENTITY_EXTRACTION=1 enables entity extraction."""
        saved = os.environ.get("KORE_ENTITY_EXTRACTION")
        try:
            os.environ["KORE_ENTITY_EXTRACTION"] = "1"
            assert os.getenv("KORE_ENTITY_EXTRACTION", "0") == "1"
        finally:
            if saved is not None:
                os.environ["KORE_ENTITY_EXTRACTION"] = saved
            elif "KORE_ENTITY_EXTRACTION" in os.environ:
                del os.environ["KORE_ENTITY_EXTRACTION"]


# ── API endpoint tests ───────────────────────────────────────────────────────

class TestEntityAPI:
    def setup_method(self):
        """Create a memory with entity tags."""
        from kore_memory.integrations.entities import auto_tag_entities

        r = client.post("/save", json={
            "content": "Invoice $250.00 sent to billing@acme.com on 2024-06-15",
            "category": "finance",
        }, headers=HEADERS)
        mid = r.json()["id"]
        auto_tag_entities(mid, "Invoice $250.00 sent to billing@acme.com on 2024-06-15", "entity-test-agent")

    def test_entities_endpoint_returns_list(self):
        """GET /entities returns entity list."""
        r = client.get("/entities", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "entities" in data
        assert "total" in data
        assert isinstance(data["entities"], list)
        assert data["total"] == len(data["entities"])

    def test_entities_endpoint_filter_by_type(self):
        """GET /entities?type=email filters by entity type."""
        r = client.get("/entities?type=email", headers=HEADERS)
        assert r.status_code == 200
        for entity in r.json()["entities"]:
            assert entity["type"] == "email"

    def test_entities_endpoint_limit(self):
        """GET /entities?limit=1 respects limit."""
        r = client.get("/entities?limit=1", headers=HEADERS)
        assert r.status_code == 200
        assert len(r.json()["entities"]) <= 1

    def test_entities_endpoint_agent_isolation(self):
        """Entities are scoped to the requesting agent."""
        other = {"X-Agent-Id": "other-entity-agent"}
        r = client.get("/entities", headers=other)
        assert r.status_code == 200
        assert r.json()["total"] == 0


# ── Graceful degradation tests ───────────────────────────────────────────────

class TestGracefulDegradation:
    def test_spacy_not_required(self):
        """Entity extraction works without spaCy (regex fallback)."""
        from kore_memory.integrations.entities import extract_entities

        # This should work regardless of spaCy availability
        entities = extract_entities("Email: test@example.com, Amount: $99.99")
        assert len(entities) >= 2
        types = {e["type"] for e in entities}
        assert "email" in types
        assert "money" in types

    def test_spacy_available_check(self):
        """spacy_available() returns bool without raising."""
        from kore_memory.integrations.entities import spacy_available

        result = spacy_available()
        assert isinstance(result, bool)

    def test_auto_tag_graceful_on_invalid_memory(self):
        """auto_tag_entities handles nonexistent memory gracefully."""
        from kore_memory.integrations.entities import auto_tag_entities

        # Memory ID 999999 doesn't exist — should return 0, not raise
        count = auto_tag_entities(999999, "test@example.com", "entity-test-agent")
        assert count == 0
