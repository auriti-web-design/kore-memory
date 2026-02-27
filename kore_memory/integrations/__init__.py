"""
Kore Memory — Framework integrations.
Optional bridges for LangChain, CrewAI, PydanticAI, OpenAI Agents SDK, and other AI frameworks.
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

    if name == "KoreChatMessageHistory":
        from .langchain import KoreChatMessageHistory

        return KoreChatMessageHistory

    if name == "kore_toolset":
        from .pydantic_ai import kore_toolset

        return kore_toolset

    if name == "create_kore_tools":
        from .pydantic_ai import create_kore_tools

        return create_kore_tools

    if name == "kore_agent_tools":
        from .openai_agents import kore_agent_tools

        return kore_agent_tools

    if name in ("extract_entities", "auto_tag_entities", "search_entities"):
        from . import entities

        return getattr(entities, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "KoreCrewAIMemory",
    "KoreLangChainMemory",
    "KoreChatMessageHistory",
    "kore_toolset",
    "create_kore_tools",
    "kore_agent_tools",
    "extract_entities",
    "auto_tag_entities",
    "search_entities",
]
