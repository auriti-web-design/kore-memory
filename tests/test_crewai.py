"""
Kore — CrewAI integration tests.
Uses unittest.mock to mock KoreClient; does NOT require crewai to be installed.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


# ── Test: graceful ImportError when crewai is not installed ─────────────────


class TestCrewAIImportFallback:
    """Verifica che il modulo si carica anche senza crewai installato."""

    def test_module_loads_without_crewai(self):
        """KoreCrewAIMemory deve essere importabile anche se crewai non e installato."""
        from kore_memory.integrations.crewai import KoreCrewAIMemory, _HAS_CREWAI

        # In CI/test environment crewai tipicamente non e installato
        assert isinstance(_HAS_CREWAI, bool)
        # La classe deve esistere in entrambi i casi
        assert KoreCrewAIMemory is not None

    def test_has_crewai_flag_false_when_missing(self):
        """Se crewai non e nel venv, _HAS_CREWAI deve essere False."""
        # Forza il reimport senza crewai
        crewai_modules = [k for k in sys.modules if k.startswith("crewai")]
        saved = {}
        for mod in crewai_modules:
            saved[mod] = sys.modules.pop(mod)

        # Anche rimuoviamo il modulo integration per forzare reimport
        integration_mod = "kore_memory.integrations.crewai"
        saved_integration = sys.modules.pop(integration_mod, None)

        try:
            with patch.dict(sys.modules, {"crewai": None, "crewai.memory": None}):
                mod = importlib.import_module(integration_mod)
                importlib.reload(mod)
                assert mod._HAS_CREWAI is False
                assert mod.KoreCrewAIMemory is not None
        finally:
            # Ripristina moduli
            for k, v in saved.items():
                sys.modules[k] = v
            if saved_integration is not None:
                sys.modules[integration_mod] = saved_integration


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Crea un KoreClient mockato."""
    with patch("kore_memory.integrations.crewai.KoreClient") as MockClientCls:
        mock_instance = MagicMock()
        MockClientCls.return_value = mock_instance
        yield mock_instance, MockClientCls


@pytest.fixture
def memory(mock_client):
    """Crea una KoreCrewAIMemory con client mockato."""
    from kore_memory.integrations.crewai import KoreCrewAIMemory

    mock_instance, _ = mock_client
    mem = KoreCrewAIMemory(
        base_url="http://localhost:9999",
        api_key="test-key",
        agent_id="crew-agent",
    )
    return mem


# ── Test: save ──────────────────────────────────────────────────────────────


class TestSave:
    """Verifica che save() invoca KoreClient.save() correttamente."""

    def test_save_basic(self, memory, mock_client):
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=1, importance=3, message="Memory saved")

        memory.save("Test memory content")

        mock_instance.save.assert_called_once_with(
            content="Test memory content",
            category="general",
            importance=1,
            ttl_hours=None,
        )

    def test_save_with_metadata(self, memory, mock_client):
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=2, importance=4, message="Memory saved")

        memory.save("Important fact", metadata={"category": "project", "importance": 4, "ttl_hours": 48})

        mock_instance.save.assert_called_once_with(
            content="Important fact",
            category="project",
            importance=4,
            ttl_hours=48,
        )

    def test_save_uses_configured_category(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=3, importance=1, message="Memory saved")

        mem = KoreCrewAIMemory(category="trading")
        mem.save("BTC at 50k")

        mock_instance.save.assert_called_once_with(
            content="BTC at 50k",
            category="trading",
            importance=1,
            ttl_hours=None,
        )


# ── Test: search ────────────────────────────────────────────────────────────


class TestSearch:
    """Verifica che search() invoca KoreClient.search() e ritorna i risultati."""

    def test_search_returns_results(self, memory, mock_client):
        mock_instance, _ = mock_client

        # Simula risultati di ricerca
        mock_record = MagicMock()
        mock_record.id = 1
        mock_record.content = "Found memory"
        mock_record.category = "general"
        mock_record.importance = 3
        mock_record.decay_score = 0.95
        mock_record.score = 0.87

        mock_response = MagicMock()
        mock_response.results = [mock_record]
        mock_instance.search.return_value = mock_response

        results = memory.search("test query", limit=3)

        mock_instance.search.assert_called_once_with(q="test query", limit=3, category=None, semantic=True)
        assert len(results) == 1
        assert results[0]["content"] == "Found memory"
        assert results[0]["id"] == 1
        assert results[0]["importance"] == 3
        assert results[0]["decay_score"] == 0.95
        assert results[0]["score"] == 0.87

    def test_search_empty_results(self, memory, mock_client):
        mock_instance, _ = mock_client

        mock_response = MagicMock()
        mock_response.results = []
        mock_instance.search.return_value = mock_response

        results = memory.search("nonexistent")

        assert results == []

    def test_search_default_limit(self, memory, mock_client):
        mock_instance, _ = mock_client

        mock_response = MagicMock()
        mock_response.results = []
        mock_instance.search.return_value = mock_response

        memory.search("query")

        mock_instance.search.assert_called_once_with(q="query", limit=5, category=None, semantic=True)


# ── Test: short-term vs long-term ───────────────────────────────────────────


class TestMemoryPatterns:
    """Verifica che short_term e long_term usano importance e TTL diversi."""

    def test_save_short_term(self, memory, mock_client):
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=10, importance=1, message="Memory saved")

        memory.save_short_term("Temporary note")

        mock_instance.save.assert_called_once_with(
            content="Temporary note",
            category="general",
            importance=1,
            ttl_hours=24,
        )

    def test_save_long_term_default_importance(self, memory, mock_client):
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=11, importance=4, message="Memory saved")

        memory.save_long_term("Critical decision: use PostgreSQL")

        mock_instance.save.assert_called_once_with(
            content="Critical decision: use PostgreSQL",
            category="general",
            importance=4,
            ttl_hours=None,
        )

    def test_save_long_term_custom_importance(self, memory, mock_client):
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=12, importance=5, message="Memory saved")

        memory.save_long_term("API credentials stored in vault", importance=5)

        mock_instance.save.assert_called_once_with(
            content="API credentials stored in vault",
            category="general",
            importance=5,
            ttl_hours=None,
        )

    def test_save_long_term_clamps_importance(self, memory, mock_client):
        """Importance viene clampata tra 2 e 5."""
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=13, importance=2, message="Memory saved")

        # importance=1 viene clampata a 2 (long-term non puo avere importance 1)
        memory.save_long_term("Should be at least 2", importance=1)

        mock_instance.save.assert_called_once_with(
            content="Should be at least 2",
            category="general",
            importance=2,
            ttl_hours=None,
        )

    def test_short_vs_long_term_difference(self, memory, mock_client):
        """Short-term ha TTL 24h + importance 1, long-term ha no TTL + importance alta."""
        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=14, importance=1, message="Memory saved")

        memory.save_short_term("Ephemeral thought")
        short_call = mock_instance.save.call_args_list[-1]

        mock_instance.save.return_value = MagicMock(id=15, importance=4, message="Memory saved")
        memory.save_long_term("Important insight")
        long_call = mock_instance.save.call_args_list[-1]

        # Short-term: low importance, has TTL
        assert short_call.kwargs["importance"] == 1
        assert short_call.kwargs["ttl_hours"] == 24

        # Long-term: high importance, no TTL
        assert long_call.kwargs["importance"] == 4
        assert long_call.kwargs["ttl_hours"] is None


# ── Test: custom category ───────────────────────────────────────────────────


class TestCustomCategory:
    """Verifica che la categoria configurata viene usata di default."""

    def test_default_category_is_general(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        mem = KoreCrewAIMemory()
        assert mem._category == "general"

    def test_custom_category_at_init(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=20, importance=1, message="Memory saved")

        mem = KoreCrewAIMemory(category="decision")
        mem.save("Chose React over Vue")

        mock_instance.save.assert_called_once_with(
            content="Chose React over Vue",
            category="decision",
            importance=1,
            ttl_hours=None,
        )

    def test_metadata_category_overrides_default(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        mock_instance, _ = mock_client
        mock_instance.save.return_value = MagicMock(id=21, importance=1, message="Memory saved")

        mem = KoreCrewAIMemory(category="general")
        mem.save("Person note", metadata={"category": "person"})

        mock_instance.save.assert_called_once_with(
            content="Person note",
            category="person",
            importance=1,
            ttl_hours=None,
        )


# ── Test: lifecycle ─────────────────────────────────────────────────────────


class TestLifecycle:
    """Verifica context manager e repr."""

    def test_context_manager(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        mock_instance, _ = mock_client

        with KoreCrewAIMemory(base_url="http://localhost:8765") as mem:
            assert mem is not None

        mock_instance.close.assert_called_once()

    def test_repr(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        mem = KoreCrewAIMemory(base_url="http://test:8765", agent_id="crew-1", category="project")
        r = repr(mem)
        assert "http://test:8765" in r
        assert "crew-1" in r
        assert "project" in r

    def test_client_constructed_with_params(self, mock_client):
        from kore_memory.integrations.crewai import KoreCrewAIMemory

        _, MockClientCls = mock_client

        KoreCrewAIMemory(
            base_url="http://myhost:1234",
            api_key="secret",
            agent_id="agent-x",
            timeout=30.0,
        )

        MockClientCls.assert_called_with(
            base_url="http://myhost:1234",
            api_key="secret",
            agent_id="agent-x",
            timeout=30.0,
        )
