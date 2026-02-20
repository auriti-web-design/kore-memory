"""
Kore — API tests
Fast, no-network, uses TestClient (ASGI in-process).
Auth: local-only mode enabled in tests (KORE_LOCAL_ONLY=1).
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# DB temporaneo + local-only mode (no auth richiesta nei test)
os.environ["KORE_DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["KORE_LOCAL_ONLY"] = "1"

from src.database import init_db  # noqa: E402
from src.main import app  # noqa: E402

# Inizializza schema — il TestClient non attiva il lifespan senza context manager
init_db()

# Header di default: namespace agent per test di isolamento
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


# ── P3: Batch API ────────────────────────────────────────────────────────────

class TestBatchSave:
    def setup_method(self):
        from src.main import _rate_buckets
        _rate_buckets.clear()

    def test_batch_save_multiple(self):
        """Salva 3 memorie in un'unica richiesta batch."""
        payload = {
            "memories": [
                {"content": "Batch memory one", "category": "general"},
                {"content": "Batch memory two", "category": "project", "importance": 3},
                {"content": "Batch memory three", "category": "finance"},
            ]
        }
        r = client.post("/save/batch", json=payload, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["total"] == 3
        assert len(data["saved"]) == 3
        # Ogni elemento ha id e importance
        for item in data["saved"]:
            assert "id" in item
            assert item["importance"] >= 1

    def test_batch_save_single(self):
        """Batch con una sola memoria — deve funzionare."""
        r = client.post("/save/batch", json={
            "memories": [{"content": "Single batch item", "category": "general"}]
        }, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["total"] == 1

    def test_batch_save_empty_rejected(self):
        """Batch vuoto — rifiutato da validazione."""
        r = client.post("/save/batch", json={"memories": []}, headers=HEADERS)
        assert r.status_code == 422

    def test_batch_save_invalid_content(self):
        """Batch con contenuto troppo corto — rifiutato."""
        r = client.post("/save/batch", json={
            "memories": [{"content": "ab", "category": "general"}]
        }, headers=HEADERS)
        assert r.status_code == 422


# ── P3: Tag system ───────────────────────────────────────────────────────────

class TestTags:
    def _create_memory(self) -> int:
        r = client.post("/save", json={"content": "Memory for tag testing purposes", "category": "general"}, headers=HEADERS)
        return r.json()["id"]

    def test_add_tags(self):
        """Aggiunge tag a una memoria."""
        mid = self._create_memory()
        r = client.post(f"/memories/{mid}/tags", json={"tags": ["python", "test"]}, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["count"] == 2
        assert "python" in data["tags"]
        assert "test" in data["tags"]

    def test_get_tags(self):
        """Legge i tag di una memoria."""
        mid = self._create_memory()
        client.post(f"/memories/{mid}/tags", json={"tags": ["alpha", "beta"]}, headers=HEADERS)
        r = client.get(f"/memories/{mid}/tags", headers=HEADERS)
        assert r.status_code == 200
        assert "alpha" in r.json()["tags"]
        assert "beta" in r.json()["tags"]

    def test_remove_tags(self):
        """Rimuove un tag specifico."""
        mid = self._create_memory()
        client.post(f"/memories/{mid}/tags", json={"tags": ["keep", "remove"]}, headers=HEADERS)
        r = client.request("DELETE", f"/memories/{mid}/tags", json={"tags": ["remove"]}, headers=HEADERS)
        assert r.status_code == 200
        assert "keep" in r.json()["tags"]
        assert "remove" not in r.json()["tags"]

    def test_search_by_tag(self):
        """Cerca memorie per tag."""
        mid = self._create_memory()
        client.post(f"/memories/{mid}/tags", json={"tags": ["unique-tag-xyz"]}, headers=HEADERS)
        r = client.get("/tags/unique-tag-xyz/memories", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        ids = [m["id"] for m in r.json()["results"]]
        assert mid in ids

    def test_tags_normalized_lowercase(self):
        """I tag vengono normalizzati in lowercase."""
        mid = self._create_memory()
        client.post(f"/memories/{mid}/tags", json={"tags": ["UPPER", "MiXeD"]}, headers=HEADERS)
        r = client.get(f"/memories/{mid}/tags", headers=HEADERS)
        tags = r.json()["tags"]
        assert "upper" in tags
        assert "mixed" in tags

    def test_tags_scoped_to_agent(self):
        """Un altro agente non può aggiungere tag a memorie altrui."""
        mid = self._create_memory()
        r = client.post(f"/memories/{mid}/tags", json={"tags": ["intruder"]}, headers=OTHER_AGENT)
        assert r.status_code == 201
        assert r.json()["count"] == 0  # nessun tag aggiunto — memoria non appartiene all'agente

    def test_duplicate_tags_ignored(self):
        """Tag duplicati vengono ignorati (INSERT OR IGNORE)."""
        mid = self._create_memory()
        client.post(f"/memories/{mid}/tags", json={"tags": ["dup"]}, headers=HEADERS)
        client.post(f"/memories/{mid}/tags", json={"tags": ["dup"]}, headers=HEADERS)
        r = client.get(f"/memories/{mid}/tags", headers=HEADERS)
        assert r.json()["tags"].count("dup") == 1


# ── P3: Relazioni ────────────────────────────────────────────────────────────

class TestRelations:
    def _create_two_memories(self) -> tuple[int, int]:
        r1 = client.post("/save", json={"content": "Source memory for relation test", "category": "general"}, headers=HEADERS)
        r2 = client.post("/save", json={"content": "Target memory for relation test", "category": "general"}, headers=HEADERS)
        return r1.json()["id"], r2.json()["id"]

    def test_add_relation(self):
        """Crea una relazione tra due memorie."""
        src, tgt = self._create_two_memories()
        r = client.post(f"/memories/{src}/relations", json={"target_id": tgt, "relation": "depends_on"}, headers=HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["total"] >= 1

    def test_get_relations(self):
        """Legge le relazioni di una memoria."""
        src, tgt = self._create_two_memories()
        client.post(f"/memories/{src}/relations", json={"target_id": tgt, "relation": "related"}, headers=HEADERS)
        r = client.get(f"/memories/{src}/relations", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        # Verifica che la relazione contenga i dati attesi
        rel = r.json()["relations"][0]
        assert "relation" in rel
        assert "related_content" in rel

    def test_relation_bidirectional_visibility(self):
        """La relazione è visibile da entrambi i lati."""
        src, tgt = self._create_two_memories()
        client.post(f"/memories/{src}/relations", json={"target_id": tgt}, headers=HEADERS)
        # Visibile dal target
        r = client.get(f"/memories/{tgt}/relations", headers=HEADERS)
        assert r.json()["total"] >= 1

    def test_relation_cross_agent_rejected(self):
        """Non si può creare relazione con memoria di un altro agente."""
        r1 = client.post("/save", json={"content": "Agent A memory for cross relation", "category": "general"}, headers=HEADERS)
        r2 = client.post("/save", json={"content": "Agent B memory for cross relation", "category": "general"}, headers=OTHER_AGENT)
        src = r1.json()["id"]
        tgt = r2.json()["id"]
        # L'agente A prova a collegare la sua memoria a quella dell'agente B
        r = client.post(f"/memories/{src}/relations", json={"target_id": tgt}, headers=HEADERS)
        assert r.status_code == 201
        # La relazione non viene creata (count < 2 nella verifica)
        assert r.json()["total"] == 0

    def test_relation_default_type(self):
        """Il tipo di relazione predefinito è 'related'."""
        src, tgt = self._create_two_memories()
        client.post(f"/memories/{src}/relations", json={"target_id": tgt}, headers=HEADERS)
        r = client.get(f"/memories/{src}/relations", headers=HEADERS)
        assert r.json()["relations"][0]["relation"] == "related"


# ── P3: TTL / Cleanup ────────────────────────────────────────────────────────

class TestTTL:
    def setup_method(self):
        """Resetta rate limiter per evitare 429 nei test TTL."""
        from src.main import _rate_buckets
        _rate_buckets.clear()

    def test_save_with_ttl(self):
        """Salva una memoria con TTL — deve essere accettata."""
        r = client.post("/save", json={
            "content": "Expiring memory with TTL",
            "category": "general",
            "ttl_hours": 24,
        }, headers=HEADERS)
        assert r.status_code == 201
        assert "id" in r.json()

    def test_save_without_ttl(self):
        """Salva senza TTL — nessun expires_at impostato."""
        r = client.post("/save", json={
            "content": "Permanent memory without TTL",
            "category": "general",
        }, headers=HEADERS)
        assert r.status_code == 201

    def test_ttl_validation_min(self):
        """TTL < 1 ora — rifiutato."""
        r = client.post("/save", json={
            "content": "Invalid TTL memory",
            "category": "general",
            "ttl_hours": 0,
        }, headers=HEADERS)
        assert r.status_code == 422

    def test_ttl_validation_max(self):
        """TTL > 8760 ore (1 anno) — rifiutato."""
        r = client.post("/save", json={
            "content": "Invalid TTL memory too long",
            "category": "general",
            "ttl_hours": 9999,
        }, headers=HEADERS)
        assert r.status_code == 422

    def test_cleanup_endpoint(self):
        """L'endpoint /cleanup risponde correttamente."""
        r = client.post("/cleanup", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "removed" in data
        assert data["removed"] >= 0

    def test_expired_memory_not_in_search(self):
        """Memorie con expires_at nel passato non appaiono nella ricerca."""
        from src.database import get_connection

        # Inserisci direttamente una memoria già scaduta
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO memories (agent_id, content, category, importance, expires_at)
                   VALUES (?, ?, ?, ?, datetime('now', '-1 hour'))""",
                ("test-agent", "Expired secret data for TTL test", "general", 3),
            )

        r = client.get("/search?q=Expired+secret+data+for+TTL&semantic=false", headers=HEADERS)
        # La memoria scaduta non deve apparire
        for result in r.json()["results"]:
            assert "Expired secret data for TTL test" not in result["content"]

    def test_cleanup_removes_expired(self):
        """Il cleanup rimuove effettivamente le memorie scadute."""
        from src.database import get_connection

        # Inserisci memoria già scaduta
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO memories (agent_id, content, category, importance, expires_at)
                   VALUES (?, ?, ?, ?, datetime('now', '-2 hours'))""",
                ("test-agent", "Cleanup target memory", "general", 1),
            )

        r = client.post("/cleanup", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["removed"] >= 1

    def test_non_expired_memory_survives_cleanup(self):
        """Memorie con TTL futuro sopravvivono al cleanup."""
        r = client.post("/save", json={
            "content": "Future TTL memory should survive cleanup",
            "category": "general",
            "ttl_hours": 8760,  # 1 anno
        }, headers=HEADERS)
        mid = r.json()["id"]

        client.post("/cleanup", headers=HEADERS)

        # La memoria deve ancora esistere — verifico con search
        sr = client.get("/search?q=Future+TTL+memory+should+survive&semantic=false", headers=HEADERS)
        ids = [m["id"] for m in sr.json()["results"]]
        assert mid in ids


# ── P3/P2: Export / Import ────────────────────────────────────────────────────

class TestExportImport:
    def test_export_returns_memories(self):
        """L'export restituisce le memorie dell'agente."""
        # Assicura che ci sia almeno una memoria
        client.post("/save", json={"content": "Export test memory data", "category": "project"}, headers=HEADERS)
        r = client.get("/export", headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert len(data["memories"]) == data["total"]

    def test_export_scoped_to_agent(self):
        """L'export non include memorie di altri agenti."""
        agent_c = {"X-Agent-Id": "export-agent-c"}
        client.post("/save", json={"content": "Agent C exclusive export data", "category": "general"}, headers=agent_c)

        r = client.get("/export", headers=OTHER_AGENT)
        for mem in r.json()["memories"]:
            assert "Agent C exclusive" not in mem["content"]

    def test_import_memories(self):
        """L'import salva le memorie correttamente."""
        payload = {
            "memories": [
                {"content": "Imported memory alpha", "category": "general", "importance": 2},
                {"content": "Imported memory beta", "category": "project", "importance": 4},
            ]
        }
        r = client.post("/import", json=payload, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["imported"] == 2

    def test_import_skips_invalid(self):
        """L'import salta record con contenuto troppo corto."""
        payload = {
            "memories": [
                {"content": "ab", "category": "general"},  # troppo corto — saltato
                {"content": "Valid imported memory content", "category": "general"},
            ]
        }
        r = client.post("/import", json=payload, headers=HEADERS)
        assert r.status_code == 201
        assert r.json()["imported"] == 1

    def test_export_excludes_expired(self):
        """L'export non include memorie con TTL scaduto."""
        from src.database import get_connection

        with get_connection() as conn:
            conn.execute(
                """INSERT INTO memories (agent_id, content, category, importance, expires_at)
                   VALUES (?, ?, ?, ?, datetime('now', '-1 hour'))""",
                ("test-agent", "Expired export exclusion test", "general", 1),
            )

        r = client.get("/export", headers=HEADERS)
        for mem in r.json()["memories"]:
            assert "Expired export exclusion test" not in mem["content"]


# ── P2: Pagination ────────────────────────────────────────────────────────────

class TestPagination:
    def setup_method(self):
        """Crea abbastanza memorie per testare la paginazione."""
        from src.main import _rate_buckets
        _rate_buckets.clear()
        for i in range(6):
            client.post("/save", json={
                "content": f"Pagination test item number {i} with unique marker PGNX",
                "category": "general",
                "importance": 3,
            }, headers=HEADERS)

    def test_search_pagination_offset(self):
        """La ricerca con offset salta i primi risultati."""
        r_full = client.get("/search?q=PGNX&limit=10&semantic=false", headers=HEADERS)
        r_offset = client.get("/search?q=PGNX&limit=3&offset=2&semantic=false", headers=HEADERS)
        assert r_offset.status_code == 200
        data = r_offset.json()
        assert data["offset"] == 2
        assert len(data["results"]) <= 3

    def test_search_has_more_flag(self):
        """has_more è True quando ci sono più risultati oltre la pagina."""
        r = client.get("/search?q=PGNX&limit=2&offset=0&semantic=false", headers=HEADERS)
        data = r.json()
        if data["total"] > 2:
            assert data["has_more"] is True

    def test_timeline_pagination(self):
        """La timeline supporta offset."""
        r = client.get("/timeline?subject=PGNX&limit=2&offset=1", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["offset"] == 1
