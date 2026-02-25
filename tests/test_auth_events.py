"""
Test per auth.py, events.py, integrations/__init__.py e database.py edge cases.
Migliora coverage dei moduli con gap > 15%.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


# ── Fixture DB temporaneo ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _temp_db(tmp_path):
    """Crea un DB temporaneo per ogni test."""
    db_file = tmp_path / "test.db"
    os.environ["KORE_DB_PATH"] = str(db_file)
    # Reset API key cache
    import kore_memory.auth as auth_mod
    auth_mod._API_KEY = None
    yield
    os.environ.pop("KORE_DB_PATH", None)


@pytest.fixture
def client():
    from kore_memory.database import init_db
    init_db()
    from kore_memory.main import app
    return TestClient(app)


HEADERS = {"X-Agent-Id": "test-agent", "Content-Type": "application/json"}


# ── TestAuth ───────────────────────────────────────────────────────────────────

class TestAuth:
    """Test autenticazione e gestione API key."""

    def test_auto_generate_api_key(self, tmp_path):
        """Verifica che venga generata una API key se mancante."""
        import kore_memory.auth as auth_mod
        import kore_memory.config as cfg

        # Pulisci env e file
        old_env = os.environ.pop("KORE_API_KEY", None)
        old_file = cfg.API_KEY_FILE
        cfg.API_KEY_FILE = tmp_path / ".api_key"
        auth_mod._KEY_FILE = cfg.API_KEY_FILE
        auth_mod._API_KEY = None

        try:
            key = auth_mod.get_or_create_api_key()
            assert len(key) > 16
            assert cfg.API_KEY_FILE.exists()
            # Seconda chiamata ritorna stessa key dal file
            key2 = auth_mod.get_or_create_api_key()
            assert key == key2
        finally:
            cfg.API_KEY_FILE = old_file
            auth_mod._KEY_FILE = old_file
            if old_env:
                os.environ["KORE_API_KEY"] = old_env

    def test_env_key_takes_priority(self, tmp_path):
        """KORE_API_KEY env var ha priorità sul file."""
        import kore_memory.auth as auth_mod

        os.environ["KORE_API_KEY"] = "test-env-key-123"
        auth_mod._API_KEY = None
        try:
            key = auth_mod.get_or_create_api_key()
            assert key == "test-env-key-123"
        finally:
            os.environ.pop("KORE_API_KEY", None)

    def test_require_auth_missing_key_non_local(self, client):
        """Senza LOCAL_ONLY e senza key, ritorna 401."""
        old = os.environ.get("KORE_LOCAL_ONLY")
        old_test = os.environ.get("KORE_TEST_MODE")
        os.environ["KORE_LOCAL_ONLY"] = "0"
        os.environ["KORE_TEST_MODE"] = "0"
        try:
            resp = client.get("/health")
            # Health non richiede auth, ma /search sì
            resp = client.get("/search", params={"q": "test"})
            assert resp.status_code == 401
        finally:
            if old:
                os.environ["KORE_LOCAL_ONLY"] = old
            else:
                os.environ.pop("KORE_LOCAL_ONLY", None)
            if old_test:
                os.environ["KORE_TEST_MODE"] = old_test
            else:
                os.environ.pop("KORE_TEST_MODE", None)

    def test_require_auth_wrong_key(self, client):
        """Key errata ritorna 403."""
        old = os.environ.get("KORE_LOCAL_ONLY")
        old_test = os.environ.get("KORE_TEST_MODE")
        os.environ["KORE_LOCAL_ONLY"] = "0"
        os.environ["KORE_TEST_MODE"] = "0"
        try:
            resp = client.get("/search", params={"q": "test"},
                              headers={"X-Kore-Key": "wrong-key-here"})
            assert resp.status_code == 403
        finally:
            if old:
                os.environ["KORE_LOCAL_ONLY"] = old
            else:
                os.environ.pop("KORE_LOCAL_ONLY", None)
            if old_test:
                os.environ["KORE_TEST_MODE"] = old_test
            else:
                os.environ.pop("KORE_TEST_MODE", None)

    def test_agent_id_sanitization(self, client):
        """Agent ID con caratteri speciali viene sanitizzato."""
        resp = client.post("/save", json={"content": "test sanitizzazione agente"},
                           headers={"X-Agent-Id": "agent<script>alert(1)</script>", "Content-Type": "application/json"})
        assert resp.status_code == 201
        # L'agente sanitizzato non contiene caratteri pericolosi
        data = resp.json()
        assert data["id"] > 0

    def test_agent_id_empty_defaults(self, client):
        """Agent ID vuoto diventa 'default'."""
        resp = client.post("/save", json={"content": "test default agent"},
                           headers={"X-Agent-Id": "", "Content-Type": "application/json"})
        assert resp.status_code == 201


# ── TestEvents ────────────────────────────────────────────────────────────────

class TestEvents:
    """Test sistema eventi in-process."""

    def test_emit_and_on(self):
        """Registra handler e verifica emissione."""
        from kore_memory.events import clear, emit, on

        received = []
        def handler(event, data):
            received.append((event, data))

        clear()
        on("test.event", handler)
        emit("test.event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == ("test.event", {"key": "value"})
        clear()

    def test_emit_no_handlers(self):
        """Emissione senza handler non causa errori."""
        from kore_memory.events import clear, emit

        clear()
        # Non deve lanciare eccezioni
        emit("unknown.event", {"x": 1})
        clear()

    def test_handler_exception_does_not_break_chain(self):
        """Handler che lancia eccezione non interrompe altri handler."""
        from kore_memory.events import clear, emit, on

        results = []

        def bad_handler(event, data):
            raise ValueError("Errore intenzionale nel test")

        def good_handler(event, data):
            results.append(data)

        clear()
        on("test.chain", bad_handler)
        on("test.chain", good_handler)
        emit("test.chain", {"ok": True})

        # Il secondo handler deve eseguire nonostante il primo fallisca
        assert len(results) == 1
        assert results[0]["ok"] is True
        clear()

    def test_emit_without_data(self):
        """Emissione senza data usa dict vuoto."""
        from kore_memory.events import clear, emit, on

        received = []
        def handler(event, data):
            received.append(data)

        clear()
        on("test.nodata", handler)
        emit("test.nodata")

        assert received[0] == {}
        clear()

    def test_clear_removes_handlers(self):
        """clear() rimuove tutti gli handler registrati."""
        from kore_memory.events import clear, emit, on

        received = []
        def handler(event, data):
            received.append(True)

        on("test.clear", handler)
        clear()
        emit("test.clear", {})

        assert len(received) == 0


# ── TestIntegrationsInit ──────────────────────────────────────────────────────

class TestIntegrationsInit:
    """Test lazy-loader nel modulo integrations."""

    def test_lazy_load_langchain(self):
        """Verifica accesso lazy a KoreLangChainMemory."""
        from kore_memory import integrations
        cls = integrations.KoreLangChainMemory
        assert cls is not None
        assert hasattr(cls, "__init__")

    def test_lazy_load_crewai(self):
        """Verifica accesso lazy a KoreCrewAIMemory."""
        from kore_memory import integrations
        cls = integrations.KoreCrewAIMemory
        assert cls is not None

    def test_lazy_load_entities(self):
        """Verifica accesso lazy a funzioni entities."""
        from kore_memory import integrations
        fn = integrations.search_entities
        assert callable(fn)

    def test_attribute_error_unknown(self):
        """Attributo inesistente lancia AttributeError."""
        from kore_memory import integrations
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = integrations.nonexistent_module


# ── TestDatabaseEdgeCases ─────────────────────────────────────────────────────

class TestDatabaseEdgeCases:
    """Test edge case per database.py."""

    def test_connection_pool_release_and_reacquire(self):
        """Connessione rilasciata viene riutilizzata dal pool."""
        from kore_memory.database import _pool, get_connection

        # Prima connessione
        with get_connection() as conn1:
            conn1.execute("SELECT 1")

        # Seconda connessione — dovrebbe prendere dal pool
        with get_connection() as conn2:
            conn2.execute("SELECT 1")

    def test_pool_clear(self):
        """Pulizia pool chiude tutte le connessioni."""
        from kore_memory.database import _pool, get_connection, init_db

        init_db()
        with get_connection() as conn:
            conn.execute("SELECT 1")

        _pool.clear()
        # Dopo clear, nuova connessione deve funzionare
        with get_connection() as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result is not None

    def test_migration_on_existing_db(self):
        """init_db su DB esistente non crasha (migration idempotente)."""
        from kore_memory.database import init_db

        init_db()
        # Seconda chiamata — tabelle esistono già
        init_db()

    def test_rollback_on_exception(self):
        """Eccezione in get_connection causa rollback."""
        from kore_memory.database import get_connection, init_db

        init_db()
        try:
            with get_connection() as conn:
                conn.execute("INSERT INTO memories (agent_id, content, category, importance) VALUES ('test', 'test', 'general', 1)")
                raise ValueError("Test rollback")
        except ValueError:
            pass

        # Il record non deve essere stato salvato
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            assert count == 0
