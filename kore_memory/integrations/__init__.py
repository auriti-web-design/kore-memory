"""
Kore Memory — Framework integrations.
Optional bridges for LangChain, CrewAI, and other AI frameworks.
Le dipendenze sono opzionali: ogni modulo gestisce l'ImportError internamente.
"""

from __future__ import annotations


def __getattr__(name: str):
    """Lazy-load integration classes to avoid hard dependencies."""

    if name == "KoreCrewAIMemory":
        from .crewai import KoreCrewAIMemory

        return KoreCrewAIMemory

    if name == "KoreLangChainMemory":
        from .langchain import KoreLangChainMemory

        return KoreLangChainMemory

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "KoreCrewAIMemory",
    "KoreLangChainMemory",
]
