"""
Kore — FastAPI application
Memory layer with decay, auto-scoring, compression, semantic search, and auth.
"""

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

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


# ── Rate limiter in-memory ───────────────────────────────────────────────────

_rate_buckets: dict[str, list[float]] = defaultdict(list)

# Limiti per endpoint (richieste / finestra in secondi)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/save": (30, 60),         # 30 req/min
    "/search": (60, 60),       # 60 req/min
    "/timeline": (60, 60),     # 60 req/min
    "/decay/run": (5, 3600),   # 5 req/ora
    "/compress": (2, 3600),    # 2 req/ora
}


def _check_rate_limit(client_ip: str, path: str) -> None:
    """Controlla rate limit per IP + path. Lancia HTTPException 429 se superato."""
    limit_conf = _RATE_LIMITS.get(path)
    if not limit_conf:
        return
    max_requests, window = limit_conf
    now = time.monotonic()
    key = f"{client_ip}:{path}"

    # Pulisci richieste scadute
    _rate_buckets[key] = [ts for ts in _rate_buckets[key] if now - ts < window]

    if len(_rate_buckets[key]) >= max_requests:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Retry later.")

    _rate_buckets[key].append(now)


# ── Security headers middleware ──────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


# ── App factory ──────────────────────────────────────────────────────────────

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
    version="0.3.1",
    lifespan=lifespan,
)

# CORS — origini configurabili via env, default restrittivo
_allowed_origins = [o.strip() for o in os.getenv("KORE_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-Kore-Key", "X-Agent-Id", "Content-Type"],
)

# Security headers su tutte le risposte
app.add_middleware(SecurityHeadersMiddleware)


# Handler globale per eccezioni non gestite — no stack trace al client
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging
    logging.error("Errore non gestito: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

# Shared auth dependencies
_Auth = Depends(require_auth)
_Agent = Depends(get_agent_id)


# ── Core endpoints ────────────────────────────────────────────────────────────

@app.post("/save", response_model=MemorySaveResponse, status_code=201)
def save(
    request: Request,
    req: MemorySaveRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySaveResponse:
    """Save a memory scoped to the requesting agent. Importance is auto-scored if omitted."""
    _check_rate_limit(request.client.host if request.client else "unknown", "/save")
    memory_id, importance = save_memory(req, agent_id=agent_id)
    return MemorySaveResponse(id=memory_id, importance=importance)


@app.get("/search", response_model=MemorySearchResponse)
def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query (any language)"),
    limit: int = Query(5, ge=1, le=20),
    category: str | None = Query(None),
    semantic: bool = Query(True),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySearchResponse:
    """Semantic search scoped to the requesting agent."""
    _check_rate_limit(request.client.host if request.client else "unknown", "/search")
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
    request: Request,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> DecayRunResponse:
    """Recalculate decay scores for agent's memories."""
    _check_rate_limit(request.client.host if request.client else "unknown", "/decay/run")
    updated = run_decay_pass(agent_id=agent_id)
    return DecayRunResponse(updated=updated)


@app.post("/compress", response_model=CompressRunResponse)
def compress(
    request: Request,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> CompressRunResponse:
    """Merge similar memories for this agent."""
    _check_rate_limit(request.client.host if request.client else "unknown", "/compress")
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
