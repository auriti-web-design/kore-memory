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
from .models import MemorySaveRequest, MemoryUpdateRequest
from .repository import (
    add_relation,
    add_tags,
    cleanup_expired,
    delete_memory,
    export_memories,
    get_timeline,
    import_memories,
    run_decay_pass,
    save_memory,
    search_by_tag,
    search_memories,
    update_memory,
)

# Inizializza DB prima di qualsiasi operazione
init_db()

mcp = FastMCP(
    "Kore Memory",
    json_response=True,
)


import re as _re
_SAFE_AGENT_RE = _re.compile(r'[^a-zA-Z0-9_\-]')


def _sanitize_agent_id(agent_id: str) -> str:
    """Sanitizza agent_id: solo caratteri alfanumerici, dash e underscore, max 64 chars."""
    safe = _SAFE_AGENT_RE.sub("", agent_id)
    return (safe or "default")[:64]


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def memory_save(
    content: str,
    category: str = "general",
    importance: int = 0,
    agent_id: str = "default",
) -> dict:
    """
    Salva un ricordo nella memoria persistente.
    L'importanza viene auto-calcolata se 0 o non specificata (1-5 = esplicita).
    Categorie: general, project, trading, finance, person, preference, task, decision.
    """
    req = MemorySaveRequest(content=content, category=category, importance=importance or None)
    mem_id, imp = save_memory(req, agent_id=_sanitize_agent_id(agent_id))
    return {"id": mem_id, "importance": imp, "message": "Memory saved"}


@mcp.tool()
def memory_search(
    query: str,
    limit: int = 5,
    category: str = "",
    semantic: bool = True,
    agent_id: str = "default",
) -> dict:
    """
    Cerca nella memoria. Supporta ricerca semantica (embedding) e full-text.
    Restituisce le memorie più rilevanti ordinate per score.
    Lascia category vuoto per cercare in tutte le categorie.
    """
    results, next_cursor, total_count = search_memories(
        query=query, limit=limit, category=category or None,
        semantic=semantic, agent_id=_sanitize_agent_id(agent_id),
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
        "total": total_count,
        "has_more": next_cursor is not None,
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
    results, next_cursor, total_count = get_timeline(
        subject=subject, limit=limit, agent_id=_sanitize_agent_id(agent_id),
    )
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
        "total": total_count,
        "has_more": next_cursor is not None,
    }


@mcp.tool()
def memory_decay_run(agent_id: str = "default") -> dict:
    """
    Ricalcola il decay score di tutte le memorie dell'agente.
    Le memorie non accedute decadono nel tempo secondo la curva di Ebbinghaus.
    """
    updated = run_decay_pass(agent_id=_sanitize_agent_id(agent_id))
    return {"updated": updated, "message": "Decay pass complete"}


@mcp.tool()
def memory_compress(agent_id: str = "default") -> dict:
    """
    Comprime memorie simili unendole in un singolo record più ricco.
    Riduce la ridondanza mantenendo le informazioni importanti.
    """
    from .compressor import run_compression
    result = run_compression(agent_id=_sanitize_agent_id(agent_id))
    return {
        "clusters_found": result.clusters_found,
        "memories_merged": result.memories_merged,
        "new_records_created": result.new_records_created,
    }


@mcp.tool()
def memory_export(agent_id: str = "default") -> dict:
    """Esporta tutte le memorie attive dell'agente per backup."""
    data = export_memories(agent_id=_sanitize_agent_id(agent_id))
    return {"memories": data, "total": len(data)}


@mcp.tool()
def memory_delete(
    memory_id: int,
    agent_id: str = "default",
) -> dict:
    """
    Elimina una memoria per id. La memoria deve appartenere all'agente specificato.
    Restituisce success=True se eliminata, False se non trovata.
    """
    deleted = delete_memory(memory_id, agent_id=_sanitize_agent_id(agent_id))
    return {
        "success": deleted,
        "message": "Memory deleted" if deleted else "Memory not found",
    }


@mcp.tool()
def memory_update(
    memory_id: int,
    content: str = "",
    category: str = "",
    importance: int = 0,
    agent_id: str = "default",
) -> dict:
    """
    Aggiorna una memoria esistente. Solo i campi forniti vengono modificati.
    Rigenera l'embedding se il contenuto cambia.
    Lascia vuoto/0 i campi che non vuoi modificare.
    """
    req = MemoryUpdateRequest(
        content=content or None,
        category=category or None,
        importance=importance or None,
    )
    updated = update_memory(memory_id, req, agent_id=_sanitize_agent_id(agent_id))
    return {
        "success": updated,
        "message": "Memory updated" if updated else "Memory not found",
    }


@mcp.tool()
def memory_save_batch(
    memories: list[dict],
    agent_id: str = "default",
) -> dict:
    """
    Salva più memorie in batch. Ogni elemento deve avere almeno 'content'.
    Campi opzionali: category (default 'general'), importance (None=auto, 1-5=esplicita).
    Massimo 100 memorie per batch.
    """
    saved = []
    errors = 0
    for mem in memories[:100]:
        content = mem.get("content", "")
        if not content or len(content.strip()) < 3:
            continue
        try:
            raw_imp = mem.get("importance")
            req = MemorySaveRequest(
                content=content,
                category=mem.get("category", "general"),
                importance=raw_imp if raw_imp and raw_imp >= 1 else None,
            )
            mem_id, imp = save_memory(req, agent_id=_sanitize_agent_id(agent_id))
            saved.append({"id": mem_id, "importance": imp})
        except Exception:
            errors += 1
    return {"saved": saved, "total": len(saved), "errors": errors}


@mcp.tool()
def memory_add_tags(
    memory_id: int,
    tags: list[str],
    agent_id: str = "default",
) -> dict:
    """
    Aggiunge tag a una memoria. I tag vengono normalizzati in minuscolo.
    Restituisce il numero di tag aggiunti.
    """
    count = add_tags(memory_id, tags, agent_id=_sanitize_agent_id(agent_id))
    return {"count": count, "message": f"{count} tags added"}


@mcp.tool()
def memory_search_by_tag(
    tag: str,
    agent_id: str = "default",
    limit: int = 20,
) -> dict:
    """
    Cerca memorie per tag. Restituisce memorie ordinate per importanza e data.
    """
    results = search_by_tag(tag, agent_id=_sanitize_agent_id(agent_id), limit=limit)
    return {
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "decay_score": r.decay_score,
                "created_at": str(r.created_at),
            }
            for r in results
        ],
        "total": len(results),
    }


@mcp.tool()
def memory_add_relation(
    source_id: int,
    target_id: int,
    relation: str = "related",
    agent_id: str = "default",
) -> dict:
    """
    Crea una relazione tra due memorie (grafo). Entrambe devono appartenere all'agente.
    Tipi comuni: related, causes, blocks, extends, contradicts.
    """
    created = add_relation(source_id, target_id, relation, agent_id=_sanitize_agent_id(agent_id))
    return {
        "success": created,
        "message": "Relation created" if created else "Failed — memories not found or not owned by agent",
    }


@mcp.tool()
def memory_cleanup(agent_id: str = "default") -> dict:
    """
    Elimina memorie con TTL scaduto per l'agente specificato.
    Restituisce il numero di record rimossi.
    """
    removed = cleanup_expired(agent_id=_sanitize_agent_id(agent_id))
    return {"removed": removed, "message": f"{removed} expired memories cleaned up"}


@mcp.tool()
def memory_import(
    memories: list[dict],
    agent_id: str = "default",
) -> dict:
    """
    Importa memorie da una lista di dict. Ogni elemento deve avere almeno 'content'.
    Campi opzionali: category, importance. Massimo 500 memorie.
    """
    count = import_memories(memories, agent_id=_sanitize_agent_id(agent_id))
    return {"imported": count, "message": f"{count} memories imported"}


# ── Resources ────────────────────────────────────────────────────────────────

@mcp.resource("kore://health")
def health_resource() -> str:
    """Stato del server Kore."""
    from . import config
    from .repository import _embeddings_available
    return (
        f"Kore v{config.VERSION} — "
        f"semantic_search={'enabled' if _embeddings_available() else 'disabled'}"
    )


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    mcp.run()


if __name__ == "__main__":
    main()
