"""
Kore — Test LangChain Integration
Verifica KoreLangChainMemory con mock del KoreClient (zero rete, zero server).

Testa:
- Graceful fallback senza langchain installato
- save_context salva via client
- load_memory_variables recupera memorie
- clear e' un no-op
- Parametri configurabili (memory_key, input_key, output_key, k, semantic, category)
"""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from kore_memory.models import MemoryRecord, MemorySaveResponse, MemorySearchResponse


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_search_response(contents: list[str]) -> MemorySearchResponse:
    """Crea una MemorySearchResponse con i contenuti forniti."""
    records = [
        MemoryRecord(
            id=i + 1,
            content=c,
            category="general",
            importance=3,
            decay_score=0.9,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            updated_at=datetime(2026, 1, 1, 12, 0, 0),
            score=0.85 - i * 0.1,
        )
        for i, c in enumerate(contents)
    ]
    return MemorySearchResponse(results=records, total=len(records))


def _make_save_response(memory_id: int = 1, importance: int = 3) -> MemorySaveResponse:
    """Crea una MemorySaveResponse di test."""
    return MemorySaveResponse(id=memory_id, importance=importance)


def _make_mock_client() -> MagicMock:
    """Crea un mock del KoreClient con risposte di default."""
    mock = MagicMock()
    mock.search.return_value = _make_search_response(["Memory about AI agents"])
    mock.save.return_value = _make_save_response()
    return mock


# ── Test: import graceful senza langchain ────────────────────────────────────


class TestImportGraceful:
    def test_import_without_langchain(self):
        """Se langchain_core non e' installato, il modulo non deve crashare."""
        # Salva e rimuovi langchain_core dal path
        saved_modules = {}
        to_remove = [key for key in sys.modules if key.startswith("langchain_core")]
        for key in to_remove:
            saved_modules[key] = sys.modules.pop(key)

        # Simula che langchain_core non sia installabile
        import importlib

        import kore_memory.integrations.langchain as lc_module

        original_has = lc_module._HAS_LANGCHAIN

        try:
            lc_module._HAS_LANGCHAIN = False

            # Il costruttore deve alzare ImportError se langchain non c'e'
            with pytest.raises(ImportError, match="langchain-core is required"):
                lc_module.KoreLangChainMemory(client=_make_mock_client())
        finally:
            lc_module._HAS_LANGCHAIN = original_has
            # Ripristina i moduli
            sys.modules.update(saved_modules)

    def test_has_langchain_flag_reflects_availability(self):
        """Il flag _HAS_LANGCHAIN riflette la disponibilita' di langchain_core."""
        from kore_memory.integrations.langchain import _HAS_LANGCHAIN

        # Se siamo qui, il flag puo' essere True o False in base all'ambiente.
        # Verifica solo che sia un booleano.
        assert isinstance(_HAS_LANGCHAIN, bool)


# ── Test: integrations __init__ export condizionale ──────────────────────────


class TestIntegrationsInit:
    def test_init_exports_list(self):
        """__init__.py deve avere __all__ come lista."""
        from kore_memory import integrations

        assert isinstance(integrations.__all__, list)

    def test_conditional_export(self):
        """Se langchain e' disponibile, KoreLangChainMemory e' in __all__."""
        from kore_memory.integrations import __all__
        from kore_memory.integrations.langchain import _HAS_LANGCHAIN

        if _HAS_LANGCHAIN:
            assert "KoreLangChainMemory" in __all__


# ── Test con mock del client (no rete, no langchain richiesto a runtime) ─────
# Questi test verificano la logica interna della classe, mockando sia il client
# Kore sia il flag _HAS_LANGCHAIN per funzionare in qualsiasi ambiente.


def _make_memory(**kwargs: object) -> object:
    """Crea un KoreLangChainMemory con _HAS_LANGCHAIN forzato a True e client mock."""
    from kore_memory.integrations.langchain import KoreLangChainMemory

    # Forza il flag per testare la logica anche senza langchain installato
    with patch("kore_memory.integrations.langchain._HAS_LANGCHAIN", True):
        if "client" not in kwargs:
            kwargs["client"] = _make_mock_client()  # type: ignore[assignment]
        return KoreLangChainMemory(**kwargs)  # type: ignore[arg-type]


class TestMemoryVariables:
    def test_default_memory_key(self):
        """memory_variables restituisce [memory_key] di default."""
        mem = _make_memory()
        assert mem.memory_variables == ["history"]

    def test_custom_memory_key(self):
        """memory_variables rispetta un memory_key personalizzato."""
        mem = _make_memory(memory_key="kore_context")
        assert mem.memory_variables == ["kore_context"]


class TestLoadMemoryVariables:
    def test_load_returns_formatted_memories(self):
        """load_memory_variables formatta i risultati come [category] content."""
        mock_client = _make_mock_client()
        mock_client.search.return_value = _make_search_response([
            "AI agents are autonomous systems",
            "Kore Memory uses Ebbinghaus decay",
        ])
        mem = _make_memory(client=mock_client)

        result = mem.load_memory_variables({"input": "Tell me about AI"})

        assert "history" in result
        assert "[general] AI agents are autonomous systems" in result["history"]
        assert "[general] Kore Memory uses Ebbinghaus decay" in result["history"]
        mock_client.search.assert_called_once_with(
            q="Tell me about AI",
            limit=5,
            semantic=True,
        )

    def test_load_with_empty_results(self):
        """Se non ci sono risultati, restituisce stringa vuota."""
        mock_client = _make_mock_client()
        mock_client.search.return_value = _make_search_response([])
        mem = _make_memory(client=mock_client)

        result = mem.load_memory_variables({"input": "something obscure"})

        assert result == {"history": ""}

    def test_load_with_empty_input(self):
        """Se l'input e' vuoto, restituisce stringa vuota senza chiamare search."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client)

        result = mem.load_memory_variables({"input": ""})

        assert result == {"history": ""}
        mock_client.search.assert_not_called()

    def test_load_uses_custom_input_key(self):
        """load_memory_variables usa l'input_key configurato."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, input_key="question")

        mem.load_memory_variables({"question": "What is Kore?"})

        mock_client.search.assert_called_once_with(
            q="What is Kore?",
            limit=5,
            semantic=True,
        )

    def test_load_uses_custom_memory_key(self):
        """Il risultato usa il memory_key configurato."""
        mem = _make_memory(memory_key="context")

        result = mem.load_memory_variables({"input": "test query"})

        assert "context" in result
        assert "history" not in result

    def test_load_respects_k_parameter(self):
        """Il parametro k viene passato come limit alla search."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, k=3)

        mem.load_memory_variables({"input": "test"})

        mock_client.search.assert_called_once_with(q="test", limit=3, semantic=True)

    def test_load_respects_semantic_toggle(self):
        """Il parametro semantic viene passato alla search."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, semantic=False)

        mem.load_memory_variables({"input": "test"})

        mock_client.search.assert_called_once_with(q="test", limit=5, semantic=False)

    def test_load_fallback_on_missing_input_key(self):
        """Se input_key non e' nel dict, concatena tutti i valori stringa."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, input_key="question")

        mem.load_memory_variables({"prompt": "Hello world"})

        mock_client.search.assert_called_once_with(
            q="Hello world",
            limit=5,
            semantic=True,
        )

    def test_load_handles_search_exception(self):
        """Se la search fallisce, restituisce stringa vuota senza propagare."""
        mock_client = _make_mock_client()
        mock_client.search.side_effect = Exception("Connection refused")
        mem = _make_memory(client=mock_client)

        result = mem.load_memory_variables({"input": "test"})

        assert result == {"history": ""}


class TestSaveContext:
    def test_save_stores_conversation_turn(self):
        """save_context salva input + output come memoria formattata."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client)

        mem.save_context(
            {"input": "What is Kore?"},
            {"output": "Kore is a memory layer for AI agents."},
        )

        mock_client.save.assert_called_once_with(
            content="Human: What is Kore?\nAI: Kore is a memory layer for AI agents.",
            category="general",
            importance=None,
        )

    def test_save_uses_custom_keys(self):
        """save_context usa input_key e output_key configurati."""
        mock_client = _make_mock_client()
        mem = _make_memory(
            client=mock_client,
            input_key="question",
            output_key="answer",
        )

        mem.save_context(
            {"question": "How does decay work?"},
            {"answer": "Ebbinghaus forgetting curve."},
        )

        mock_client.save.assert_called_once_with(
            content="Human: How does decay work?\nAI: Ebbinghaus forgetting curve.",
            category="general",
            importance=None,
        )

    def test_save_uses_custom_category(self):
        """save_context usa la category configurata."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, category="project")

        mem.save_context({"input": "test"}, {"output": "response"})

        mock_client.save.assert_called_once_with(
            content="Human: test\nAI: response",
            category="project",
            importance=None,
        )

    def test_save_auto_importance_enabled(self):
        """Con auto_importance=True, importance viene inviata come None (auto-scored dal server)."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, auto_importance=True)

        mem.save_context({"input": "test"}, {"output": "response"})

        call_kwargs = mock_client.save.call_args[1]
        assert call_kwargs["importance"] is None

    def test_save_auto_importance_disabled(self):
        """Con auto_importance=False, importance viene inviata come 2."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client, auto_importance=False)

        mem.save_context({"input": "test"}, {"output": "response"})

        call_kwargs = mock_client.save.call_args[1]
        assert call_kwargs["importance"] == 2

    def test_save_skips_empty_content(self):
        """Se sia input che output sono vuoti, non salva nulla."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client)

        mem.save_context({"input": ""}, {"output": ""})

        mock_client.save.assert_not_called()

    def test_save_only_input(self):
        """Salva anche se c'e' solo l'input senza output."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client)

        mem.save_context({"input": "Hello"}, {"output": ""})

        mock_client.save.assert_called_once_with(
            content="Human: Hello",
            category="general",
            importance=None,
        )

    def test_save_handles_exception(self):
        """Se il save fallisce, non propaga l'eccezione."""
        mock_client = _make_mock_client()
        mock_client.save.side_effect = Exception("Connection refused")
        mem = _make_memory(client=mock_client)

        # Non deve alzare eccezione
        mem.save_context({"input": "test"}, {"output": "response"})


class TestClear:
    def test_clear_is_noop(self):
        """clear() non fa nulla — Kore gestisce il decay automaticamente."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client)

        # Non deve alzare eccezione ne' chiamare metodi sul client
        mem.clear()

        # Verifica che nessun metodo del client sia stato chiamato
        mock_client.assert_not_called()
        mock_client.delete.assert_not_called()


class TestConstructor:
    def test_default_parameters(self):
        """Verifica i valori di default del costruttore."""
        mem = _make_memory()

        assert mem._memory_key == "history"
        assert mem._input_key == "input"
        assert mem._output_key == "output"
        assert mem._k == 5
        assert mem._semantic is True
        assert mem._category == "general"
        assert mem._auto_importance is True

    def test_custom_parameters(self):
        """Verifica che tutti i parametri custom vengano applicati."""
        mem = _make_memory(
            memory_key="kore_ctx",
            input_key="question",
            output_key="answer",
            k=10,
            semantic=False,
            category="trading",
            auto_importance=False,
        )

        assert mem._memory_key == "kore_ctx"
        assert mem._input_key == "question"
        assert mem._output_key == "answer"
        assert mem._k == 10
        assert mem._semantic is False
        assert mem._category == "trading"
        assert mem._auto_importance is False

    def test_accepts_external_client(self):
        """Accetta un KoreClient esterno via parametro client."""
        mock_client = _make_mock_client()
        mem = _make_memory(client=mock_client)

        assert mem._client is mock_client

    def test_creates_client_from_params(self):
        """Senza client esterno, ne crea uno con i parametri forniti."""
        with patch("kore_memory.integrations.langchain._HAS_LANGCHAIN", True), \
             patch("kore_memory.integrations.langchain.KoreClient") as MockClient:
            MockClient.return_value = MagicMock()

            from kore_memory.integrations.langchain import KoreLangChainMemory

            mem = KoreLangChainMemory(
                base_url="http://custom:9000",
                api_key="my-key",
                agent_id="test-agent",
            )

            MockClient.assert_called_once_with(
                base_url="http://custom:9000",
                api_key="my-key",
                agent_id="test-agent",
            )
