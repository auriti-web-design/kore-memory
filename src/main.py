"""
Kore — FastAPI application
Memory layer with decay, auto-scoring, compression, semantic search, and auth.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .auth import get_agent_id, require_auth
from .database import init_db
from .models import (
    CompressRunResponse,
    DecayRunResponse,
    MemorySaveRequest,
    MemorySaveResponse,
    MemorySearchResponse,
)
from .repository import (
    delete_memory,
    get_timeline,
    run_decay_pass,
    save_memory,
    search_memories,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Kore",
    description=(
        "The memory layer that thinks like a human: "
        "remembers what matters, forgets what doesn't, and never calls home."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# Shared auth dependencies
_Auth = Depends(require_auth)
_Agent = Depends(get_agent_id)


# ── Core endpoints ────────────────────────────────────────────────────────────

@app.post("/save", response_model=MemorySaveResponse, status_code=201)
def save(
    req: MemorySaveRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySaveResponse:
    """Save a memory scoped to the requesting agent. Importance is auto-scored if omitted."""
    from .scorer import auto_score
    importance = req.importance if req.importance > 1 else auto_score(req.content, req.category)
    memory_id = save_memory(req, agent_id=agent_id)
    return MemorySaveResponse(id=memory_id, importance=importance)


@app.get("/search", response_model=MemorySearchResponse)
def search(
    q: str = Query(..., min_length=1, description="Search query (any language)"),
    limit: int = Query(5, ge=1, le=20),
    category: str | None = Query(None),
    semantic: bool = Query(True),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySearchResponse:
    """Semantic search scoped to the requesting agent."""
    results = search_memories(query=q, limit=limit, category=category, semantic=semantic, agent_id=agent_id)
    return MemorySearchResponse(results=results, total=len(results))


@app.get("/timeline", response_model=MemorySearchResponse)
def timeline(
    subject: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySearchResponse:
    """Chronological memory history for a subject, scoped to agent."""
    results = get_timeline(subject=subject, limit=limit, agent_id=agent_id)
    return MemorySearchResponse(results=results, total=len(results))


@app.delete("/memories/{memory_id}", status_code=204)
def delete(
    memory_id: int,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> None:
    """Delete a memory. Agents can only delete their own memories."""
    if not delete_memory(memory_id, agent_id=agent_id):
        raise HTTPException(status_code=404, detail="Memory not found")


# ── Maintenance endpoints ─────────────────────────────────────────────────────

@app.post("/decay/run", response_model=DecayRunResponse)
def decay_run(
    _: str = _Auth,
    agent_id: str = _Agent,
) -> DecayRunResponse:
    """Recalculate decay scores for agent's memories."""
    updated = run_decay_pass(agent_id=agent_id)
    return DecayRunResponse(updated=updated)


@app.post("/compress", response_model=CompressRunResponse)
def compress(
    _: str = _Auth,
    agent_id: str = _Agent,
) -> CompressRunResponse:
    """Merge similar memories for this agent."""
    from .compressor import run_compression
    result = run_compression(agent_id=agent_id)
    return CompressRunResponse(
        clusters_found=result.clusters_found,
        memories_merged=result.memories_merged,
        new_records_created=result.new_records_created,
    )


# ── Utility ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> JSONResponse:
    from .repository import _embeddings_available
    return JSONResponse({
        "status": "ok",
        "version": app.version,
        "semantic_search": _embeddings_available(),
    })
