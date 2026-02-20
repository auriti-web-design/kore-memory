"""
Kore — Server MCP (Model Context Protocol)
Espone save, search, timeline, decay e compress come tools MCP
per integrazione diretta con Claude, Cursor, e altri client MCP.

Uso:
  python -m src.mcp_server                     # stdio (default)
  python -m src.mcp_server --transport sse      # SSE per web
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .database import init_db
from .models import MemorySaveRequest
from .repository import (
    export_memories,
    get_timeline,
    run_decay_pass,
    save_memory,
    search_memories,
)

# Inizializza DB prima di qualsiasi operazione
init_db()

mcp = FastMCP(
    "Kore Memory",
    json_response=True,
)


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def memory_save(
    content: str,
    category: str = "general",
    importance: int = 1,
    agent_id: str = "default",
) -> dict:
    """
    Salva un ricordo nella memoria persistente.
    L'importanza viene auto-calcolata se impostata a 1.
    Categorie: general, project, trading, finance, person, preference, task, decision.
    """
    req = MemorySaveRequest(content=content, category=category, importance=importance)
    mem_id, imp = save_memory(req, agent_id=agent_id)
    return {"id": mem_id, "importance": imp, "message": "Memory saved"}


@mcp.tool()
def memory_search(
    query: str,
    limit: int = 5,
    category: str | None = None,
    semantic: bool = True,
    agent_id: str = "default",
) -> dict:
    """
    Cerca nella memoria. Supporta ricerca semantica (embedding) e full-text.
    Restituisce le memorie più rilevanti ordinate per score.
    """
    results = search_memories(
        query=query, limit=limit, category=category,
        semantic=semantic, agent_id=agent_id,
    )
    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "decay_score": r.decay_score,
                "score": r.score,
                "created_at": str(r.created_at),
            }
            for r in results
        ],
        "total": len(results),
    }


@mcp.tool()
def memory_timeline(
    subject: str,
    limit: int = 20,
    agent_id: str = "default",
) -> dict:
    """
    Cronologia delle memorie su un argomento, ordinate dal più vecchio al più recente.
    Utile per ricostruire la storia di un progetto o una persona.
    """
    results = get_timeline(subject=subject, limit=limit, agent_id=agent_id)
    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "created_at": str(r.created_at),
            }
            for r in results
        ],
        "total": len(results),
    }


@mcp.tool()
def memory_decay_run(agent_id: str = "default") -> dict:
    """
    Ricalcola il decay score di tutte le memorie dell'agente.
    Le memorie non accedute decadono nel tempo secondo la curva di Ebbinghaus.
    """
    updated = run_decay_pass(agent_id=agent_id)
    return {"updated": updated, "message": "Decay pass complete"}


@mcp.tool()
def memory_compress(agent_id: str = "default") -> dict:
    """
    Comprime memorie simili unendole in un singolo record più ricco.
    Riduce la ridondanza mantenendo le informazioni importanti.
    """
    from .compressor import run_compression
    result = run_compression(agent_id=agent_id)
    return {
        "clusters_found": result.clusters_found,
        "memories_merged": result.memories_merged,
        "new_records_created": result.new_records_created,
    }


@mcp.tool()
def memory_export(agent_id: str = "default") -> dict:
    """Esporta tutte le memorie attive dell'agente per backup."""
    data = export_memories(agent_id=agent_id)
    return {"memories": data, "total": len(data)}


# ── Resources ────────────────────────────────────────────────────────────────

@mcp.resource("kore://health")
def health_resource() -> str:
    """Stato del server Kore."""
    from .repository import _embeddings_available
    from . import config
    return (
        f"Kore v{config.VERSION} — "
        f"semantic_search={'enabled' if _embeddings_available() else 'disabled'}"
    )


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    mcp.run()


if __name__ == "__main__":
    main()
