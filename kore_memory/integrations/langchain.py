"""
Kore — LangChain Integration
Integrazione con LangChain tramite BaseMemory.

Permette di usare Kore come memory backend per chain e agent LangChain.
Richiede `langchain-core>=0.2.0` (opzionale).

Uso:
    from kore_memory.integrations.langchain import KoreLangChainMemory

    memory = KoreLangChainMemory(
        base_url="http://localhost:8765",
        agent_id="my-agent",
        semantic=True,
    )

    # In una LangChain chain:
    chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from langchain_core.memory import BaseMemory

    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False
    BaseMemory = object  # type: ignore[assignment,misc]

from kore_memory.client import KoreClient

logger = logging.getLogger(__name__)


class KoreLangChainMemory(BaseMemory):  # type: ignore[misc]
    """
    LangChain memory backend che usa Kore Memory per persistenza.

    Salva automaticamente i turni di conversazione (input/output) come memorie
    in Kore, e recupera le memorie rilevanti durante load_memory_variables
    usando ricerca semantica o FTS5.

    Args:
        base_url: URL del server Kore (default: http://localhost:8765)
        api_key: API key per autenticazione (opzionale su localhost)
        agent_id: Namespace agente (default: "default")
        memory_key: Chiave usata per iniettare memorie nel prompt (default: "history")
        input_key: Chiave dell'input nella chain (default: "input")
        output_key: Chiave dell'output nella chain (default: "output")
        k: Numero massimo di risultati da recuperare (default: 5)
        semantic: Usa ricerca semantica se disponibile (default: True)
        category: Categoria per le memorie salvate (default: "general")
        auto_importance: Usa auto-scoring importanza (default: True)
    """

    # -- Campi di configurazione (non-Pydantic, gestiti manualmente) ----------
    # Nota: BaseMemory usa Pydantic v1 internamente in alcune versioni di
    # langchain-core; per massima compatibilita' usiamo attributi semplici.

    _client: KoreClient
    _memory_key: str
    _input_key: str
    _output_key: str
    _k: int
    _semantic: bool
    _category: str
    _auto_importance: bool

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        api_key: str | None = None,
        agent_id: str = "default",
        memory_key: str = "history",
        input_key: str = "input",
        output_key: str = "output",
        k: int = 5,
        semantic: bool = True,
        category: str = "general",
        auto_importance: bool = True,
        *,
        client: KoreClient | None = None,
    ):
        if not _HAS_LANGCHAIN:
            raise ImportError(
                "langchain-core is required for KoreLangChainMemory. "
                "Install it with: pip install 'kore-memory[langchain]'"
            )

        # Inizializza BaseMemory (Pydantic v1 in langchain-core < 0.3)
        super().__init__()

        # Client Kore: usa quello fornito oppure ne crea uno nuovo
        self._client = client or KoreClient(
            base_url=base_url,
            api_key=api_key,
            agent_id=agent_id,
        )
        self._memory_key = memory_key
        self._input_key = input_key
        self._output_key = output_key
        self._k = k
        self._semantic = semantic
        self._category = category
        self._auto_importance = auto_importance

    # -- Proprieta' richieste da BaseMemory -----------------------------------

    @property
    def memory_variables(self) -> list[str]:
        """Restituisce le chiavi che questa memoria inietta nel prompt."""
        return [self._memory_key]

    # -- Metodi richiesti da BaseMemory ---------------------------------------

    def load_memory_variables(self, inputs: dict[str, Any]) -> dict[str, str]:
        """
        Recupera memorie rilevanti da Kore basandosi sull'input corrente.

        Cerca nel database Kore usando il valore dell'input_key come query.
        Restituisce un dict con memory_key -> stringa formattata delle memorie.
        """
        query = self._extract_query(inputs)
        if not query:
            return {self._memory_key: ""}

        try:
            response = self._client.search(
                q=query,
                limit=self._k,
                semantic=self._semantic,
            )
            if not response.results:
                return {self._memory_key: ""}

            # Formatta le memorie come testo leggibile
            lines: list[str] = []
            for mem in response.results:
                lines.append(f"[{mem.category}] {mem.content}")

            return {self._memory_key: "\n".join(lines)}

        except Exception:
            logger.warning("Kore memory search failed, returning empty context", exc_info=True)
            return {self._memory_key: ""}

    def save_context(self, inputs: dict[str, Any], outputs: dict[str, str]) -> None:
        """
        Salva il turno di conversazione (input + output) come memoria in Kore.

        Combina input e output in un singolo record di memoria per il retrieval futuro.
        """
        input_text = self._extract_query(inputs)
        output_text = outputs.get(self._output_key, "")

        if not input_text and not output_text:
            return

        # Combina input e output in un formato strutturato
        parts: list[str] = []
        if input_text:
            parts.append(f"Human: {input_text}")
        if output_text:
            parts.append(f"AI: {output_text}")

        content = "\n".join(parts)

        # Importance 1 = auto-scored dal server se auto_importance e' abilitato
        importance = 1 if self._auto_importance else 2

        try:
            self._client.save(
                content=content,
                category=self._category,
                importance=importance,
            )
        except Exception:
            logger.warning("Kore memory save failed", exc_info=True)

    def clear(self) -> None:
        """
        No-op: Kore gestisce il decay delle memorie automaticamente.

        Le memorie obsolete vengono dimenticate tramite la curva di Ebbinghaus,
        quindi non serve un clear esplicito. Per forzare la pulizia, usa
        direttamente il client Kore (decay_run, compress, cleanup).
        """

    # -- Helpers privati -------------------------------------------------------

    def _extract_query(self, inputs: dict[str, Any]) -> str:
        """Estrae la query dall'input dict, con fallback su tutti i valori."""
        if self._input_key in inputs:
            return str(inputs[self._input_key])

        # Fallback: concatena tutti i valori stringa dell'input
        text_parts = [str(v) for v in inputs.values() if isinstance(v, str)]
        return " ".join(text_parts)
