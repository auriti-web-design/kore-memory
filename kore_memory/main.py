"""
Kore — FastAPI application
Memory layer with decay, auto-scoring, compression, semantic search, and auth.
"""

import secrets

# ── Rate limiter in-memory ───────────────────────────────────────────────────
import threading as _rl_threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from . import config
from .auth import get_agent_id, require_auth
from .dashboard import get_dashboard_html
from .database import init_db
from .models import (
    AutoTuneResponse,
    BatchSaveRequest,
    BatchSaveResponse,
    CleanupExpiredResponse,
    CompressRunResponse,
    DecayRunResponse,
    MemoryExportResponse,
    MemoryImportRequest,
    MemoryImportResponse,
    MemorySaveRequest,
    MemorySaveResponse,
    MemorySearchResponse,
    MemoryUpdateRequest,
    RelationRequest,
    RelationResponse,
    ScoringStatsResponse,
    SessionCreateRequest,
    SessionSummaryResponse,
    TagRequest,
    TagResponse,
)
from .repository import (
    add_relation,
    add_tags,
    archive_memory,
    cleanup_expired,
    create_session,
    delete_memory,
    delete_session,
    end_session,
    export_memories,
    get_archived,
    get_relations,
    get_session_memories,
    get_session_summary,
    get_tags,
    get_timeline,
    import_memories,
    list_agents,
    list_sessions,
    remove_tags,
    restore_memory,
    run_decay_pass,
    save_memory,
    save_memory_batch,
    search_by_tag,
    search_memories,
    update_memory,
)

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_rate_lock = _rl_threading.Lock()
_rate_last_cleanup = 0.0


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind trusted proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the chain is the original client
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(client_ip: str, path: str) -> None:
    """Controlla rate limit per IP + path. Lancia HTTPException 429 se superato."""
    limit_conf = config.RATE_LIMITS.get(path)
    if not limit_conf:
        return
    max_requests, window = limit_conf
    now = time.monotonic()
    key = f"{client_ip}:{path}"

    with _rate_lock:
        # Cleanup periodico di bucket vecchi (ogni 60s) — previene memory leak
        global _rate_last_cleanup
        if now - _rate_last_cleanup > 60:
            stale_keys = [k for k, timestamps in _rate_buckets.items()
                          if not timestamps or now - timestamps[-1] > window]
            for k in stale_keys:
                del _rate_buckets[k]
            _rate_last_cleanup = now

        # Pulisci richieste scadute per questo bucket
        _rate_buckets[key] = [ts for ts in _rate_buckets[key] if now - ts < window]

        if len(_rate_buckets[key]) >= max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Retry later.")

        _rate_buckets[key].append(now)


# ── Security headers middleware ──────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    _API_CSP = "default-src 'none'; frame-ancestors 'none'"

    @staticmethod
    def _dashboard_csp(nonce: str) -> str:
        """Build CSP for dashboard with per-request nonce instead of unsafe-inline scripts."""
        return (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            f"script-src 'nonce-{nonce}'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a per-request nonce and store it for the dashboard endpoint
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # CSP with nonce for the dashboard, restrictive for APIs
        if request.url.path == "/dashboard":
            response.headers["Content-Security-Policy"] = self._dashboard_csp(nonce)
        else:
            response.headers["Content-Security-Policy"] = self._API_CSP
        return response


# ── App factory ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Initialize API key (auto-generate if missing)
    from .auth import get_or_create_api_key
    get_or_create_api_key()
    # Enable audit log if configured
    if config.AUDIT_LOG:
        from .audit import register_audit_handler
        register_audit_handler()
    yield


app = FastAPI(
    title="Kore",
    description=(
        "The memory layer that thinks like a human: "
        "remembers what matters, forgets what doesn't, and never calls home."
    ),
    version=config.VERSION,
    lifespan=lifespan,
)

# CORS — origini configurabili via env, default restrittivo
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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
    """Save a memory scoped to the requesting agent. Importance is auto-scored if omitted.
    Use X-Session-Id header to associate the memory with a conversation session."""
    _check_rate_limit(_get_client_ip(request), "/save")
    session_id = request.headers.get("X-Session-Id")
    memory_id, importance = save_memory(req, agent_id=agent_id, session_id=session_id)
    return MemorySaveResponse(id=memory_id, importance=importance)


@app.post("/save/batch", response_model=BatchSaveResponse, status_code=201)
def save_batch(
    request: Request,
    req: BatchSaveRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> BatchSaveResponse:
    """Salva più memorie in una sola richiesta (max 100). Usa batch embedding."""
    _check_rate_limit(_get_client_ip(request), "/save")
    results = save_memory_batch(req.memories, agent_id=agent_id)
    saved = [MemorySaveResponse(id=mid, importance=imp) for mid, imp in results]
    return BatchSaveResponse(saved=saved, total=len(saved))


@app.get("/search", response_model=MemorySearchResponse)
def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query (any language)"),
    limit: int = Query(5, ge=1, le=20),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
    category: str | None = Query(None),
    semantic: bool = Query(True),
    _: str = _Auth,
    agent_id: str = _Agent,
    # Deprecated params for backwards compatibility
    offset: int = Query(0, ge=0, deprecated=True, description="Deprecated: use cursor"),
) -> MemorySearchResponse:
    """Semantic search scoped to the requesting agent, with cursor-based pagination."""
    _check_rate_limit(_get_client_ip(request), "/search")

    # Parse cursor (base64 encoded tuple of decay_score, id)
    cursor_tuple = None
    if cursor:
        try:
            import base64
            import json
            decoded = base64.b64decode(cursor).decode('utf-8')
            cursor_tuple = tuple(json.loads(decoded))
        except Exception:
            raise HTTPException(400, "Invalid cursor format")

    # Execute search with cursor
    results, next_cursor, total_count = search_memories(
        query=q,
        limit=limit,
        category=category,
        semantic=semantic,
        agent_id=agent_id,
        cursor=cursor_tuple,
    )

    # Encode next cursor
    cursor_str = None
    if next_cursor:
        import base64
        import json
        cursor_str = base64.b64encode(
            json.dumps(next_cursor).encode('utf-8')
        ).decode('utf-8')

    return MemorySearchResponse(
        results=results,
        total=total_count,
        cursor=cursor_str,
        has_more=next_cursor is not None,
        offset=offset,  # Keep for backwards compat
    )


@app.get("/timeline", response_model=MemorySearchResponse)
def timeline(
    request: Request,
    subject: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
    _: str = _Auth,
    agent_id: str = _Agent,
    offset: int = Query(0, ge=0, deprecated=True, description="Deprecated: use cursor"),
) -> MemorySearchResponse:
    """Chronological memory history for a subject, scoped to agent, with cursor-based pagination."""
    _check_rate_limit(_get_client_ip(request), "/timeline")

    # Parse cursor
    cursor_tuple = None
    if cursor:
        try:
            import base64
            import json
            decoded = base64.b64decode(cursor).decode('utf-8')
            cursor_tuple = tuple(json.loads(decoded))
        except Exception:
            raise HTTPException(400, "Invalid cursor format")

    results, next_cursor, total_count = get_timeline(subject=subject, limit=limit, agent_id=agent_id, cursor=cursor_tuple)

    # Encode next cursor
    cursor_str = None
    if next_cursor:
        import base64
        import json
        cursor_str = base64.b64encode(
            json.dumps(next_cursor).encode('utf-8')
        ).decode('utf-8')

    return MemorySearchResponse(
        results=results,
        total=total_count,
        cursor=cursor_str,
        has_more=next_cursor is not None,
        offset=offset,
    )


@app.put("/memories/{memory_id}", response_model=MemorySaveResponse)
def update(
    memory_id: int,
    req: MemoryUpdateRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySaveResponse:
    """Update a memory's content, category, or importance. Agents can only update their own memories."""
    if not update_memory(memory_id, req, agent_id=agent_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemorySaveResponse(id=memory_id, importance=req.importance or 0, message="Memory updated")


@app.delete("/memories/{memory_id}", status_code=204)
def delete(
    memory_id: int,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> None:
    """Delete a memory. Agents can only delete their own memories."""
    if not delete_memory(memory_id, agent_id=agent_id):
        raise HTTPException(status_code=404, detail="Memory not found")


# ── Tag endpoints ─────────────────────────────────────────────────────────────

@app.post("/memories/{memory_id}/tags", response_model=TagResponse, status_code=201)
def tag_add(
    memory_id: int,
    req: TagRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> TagResponse:
    """Aggiunge tag a una memoria."""
    count = add_tags(memory_id, req.tags, agent_id=agent_id)
    tags = get_tags(memory_id, agent_id=agent_id)
    return TagResponse(count=count, tags=tags)


@app.delete("/memories/{memory_id}/tags", response_model=TagResponse)
def tag_remove(
    memory_id: int,
    req: TagRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> TagResponse:
    """Rimuove tag da una memoria."""
    remove_tags(memory_id, req.tags, agent_id=agent_id)
    tags = get_tags(memory_id, agent_id=agent_id)
    return TagResponse(count=len(tags), tags=tags)


@app.get("/memories/{memory_id}/tags", response_model=TagResponse)
def tag_list(
    memory_id: int,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> TagResponse:
    """Restituisce i tag di una memoria (solo se appartiene all'agent)."""
    tags = get_tags(memory_id, agent_id=agent_id)
    return TagResponse(count=len(tags), tags=tags)


@app.get("/tags/{tag}/memories", response_model=MemorySearchResponse)
def tag_search(
    tag: str,
    limit: int = Query(20, ge=1, le=50),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySearchResponse:
    """Cerca memorie per tag."""
    results = search_by_tag(tag, agent_id=agent_id, limit=limit)
    return MemorySearchResponse(results=results, total=len(results))


# ── Relation endpoints ───────────────────────────────────────────────────────

@app.post("/memories/{memory_id}/relations", response_model=RelationResponse, status_code=201)
def relation_add(
    memory_id: int,
    req: RelationRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> RelationResponse:
    """Crea una relazione tra due memorie."""
    add_relation(memory_id, req.target_id, req.relation, agent_id=agent_id)
    relations = get_relations(memory_id, agent_id=agent_id)
    return RelationResponse(relations=relations, total=len(relations))


@app.get("/memories/{memory_id}/relations", response_model=RelationResponse)
def relation_list(
    memory_id: int,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> RelationResponse:
    """Restituisce le relazioni di una memoria."""
    relations = get_relations(memory_id, agent_id=agent_id)
    return RelationResponse(relations=relations, total=len(relations))


# ── Maintenance endpoints ─────────────────────────────────────────────────────

@app.post("/decay/run", response_model=DecayRunResponse)
def decay_run(
    request: Request,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> DecayRunResponse:
    """Recalculate decay scores for agent's memories."""
    _check_rate_limit(_get_client_ip(request), "/decay/run")
    updated = run_decay_pass(agent_id=agent_id)
    return DecayRunResponse(updated=updated)


@app.post("/compress", response_model=CompressRunResponse)
def compress(
    request: Request,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> CompressRunResponse:
    """Merge similar memories for this agent."""
    _check_rate_limit(_get_client_ip(request), "/compress")
    from .compressor import run_compression
    result = run_compression(agent_id=agent_id)
    return CompressRunResponse(
        clusters_found=result.clusters_found,
        memories_merged=result.memories_merged,
        new_records_created=result.new_records_created,
    )


@app.post("/cleanup", response_model=CleanupExpiredResponse)
def cleanup(
    _: str = _Auth,
    agent_id: str = _Agent,
) -> CleanupExpiredResponse:
    """Remove expired memories (TTL scaduto) for this agent."""
    removed = cleanup_expired(agent_id=agent_id)
    return CleanupExpiredResponse(removed=removed)


@app.post("/auto-tune", response_model=AutoTuneResponse)
def auto_tune(
    request: Request,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> AutoTuneResponse:
    """Auto-tune memory importance based on access patterns."""
    _check_rate_limit(_get_client_ip(request), "/decay/run")  # share decay rate limit
    from .auto_tuner import run_auto_tune
    result = run_auto_tune(agent_id=agent_id)
    return AutoTuneResponse(**result)


@app.get("/stats/scoring", response_model=ScoringStatsResponse)
def scoring_stats(
    _: str = _Auth,
    agent_id: str = _Agent,
) -> ScoringStatsResponse:
    """Return importance scoring statistics for the agent's memories."""
    from .auto_tuner import get_scoring_stats
    return ScoringStatsResponse(**get_scoring_stats(agent_id=agent_id))


# ── Backup / Import ──────────────────────────────────────────────────────────

@app.get("/export", response_model=MemoryExportResponse)
def export(
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemoryExportResponse:
    """Esporta tutte le memorie attive dell'agente (senza embedding)."""
    data = export_memories(agent_id=agent_id)
    return MemoryExportResponse(memories=data, total=len(data))


@app.post("/import", response_model=MemoryImportResponse, status_code=201)
def import_data(
    req: MemoryImportRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemoryImportResponse:
    """Importa memorie da un export precedente."""
    count = import_memories(req.memories, agent_id=agent_id)
    return MemoryImportResponse(imported=count)


# ── Archive endpoints ──────────────────────────────────────────────────────

@app.post("/memories/{memory_id}/archive", status_code=200)
def archive(memory_id: int, _: str = _Auth, agent_id: str = _Agent) -> dict:
    if not archive_memory(memory_id, agent_id=agent_id):
        raise HTTPException(404, "Memory not found or already archived")
    return {"success": True, "message": "Memory archived"}


@app.post("/memories/{memory_id}/restore", status_code=200)
def restore(memory_id: int, _: str = _Auth, agent_id: str = _Agent) -> dict:
    if not restore_memory(memory_id, agent_id=agent_id):
        raise HTTPException(404, "Memory not found or not archived")
    return {"success": True, "message": "Memory restored"}


@app.get("/archive", response_model=MemorySearchResponse)
def archive_list(limit: int = Query(50, ge=1, le=100), _: str = _Auth, agent_id: str = _Agent) -> MemorySearchResponse:
    results = get_archived(agent_id=agent_id, limit=limit)
    return MemorySearchResponse(results=results, total=len(results))


# ── Session endpoints ─────────────────────────────────────────────────────────

@app.post("/sessions", status_code=201)
def session_create(
    req: SessionCreateRequest,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> dict:
    """Create a new conversation session."""
    result = create_session(req.session_id, agent_id=agent_id, title=req.title)
    if not result:
        raise HTTPException(400, "Failed to create session")
    return result


@app.get("/sessions")
def sessions_list(
    limit: int = Query(50, ge=1, le=200),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> list[dict]:
    """List all sessions for the requesting agent."""
    return list_sessions(agent_id=agent_id, limit=limit)


@app.get("/sessions/{session_id}/memories", response_model=MemorySearchResponse)
def session_memories(
    session_id: str,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> MemorySearchResponse:
    """Get all memories in a session."""
    results = get_session_memories(session_id, agent_id=agent_id)
    return MemorySearchResponse(results=results, total=len(results))


@app.get("/sessions/{session_id}/summary", response_model=SessionSummaryResponse)
def session_summary(
    session_id: str,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> SessionSummaryResponse:
    """Get aggregated summary of a session (no LLM)."""
    summary = get_session_summary(session_id, agent_id=agent_id)
    if not summary:
        raise HTTPException(404, "Session not found")
    return SessionSummaryResponse(**summary)


@app.post("/sessions/{session_id}/end")
def session_end(
    session_id: str,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> dict:
    """Mark a session as ended."""
    if not end_session(session_id, agent_id=agent_id):
        raise HTTPException(404, "Session not found or already ended")
    return {"success": True, "message": "Session ended"}


@app.delete("/sessions/{session_id}", status_code=200)
def session_delete(
    session_id: str,
    _: str = _Auth,
    agent_id: str = _Agent,
) -> dict:
    """Delete a session. Memories are unlinked but not deleted."""
    unlinked = delete_session(session_id, agent_id=agent_id)
    return {"success": True, "unlinked_memories": unlinked}


# ── Entity extraction ─────────────────────────────────────────────────────────

@app.get("/entities")
def entities_list(
    type: str | None = Query(None, description="Filter by entity type (person, org, email, url, date, money, location, product)"),
    limit: int = Query(50, ge=1, le=200),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> dict:
    """List extracted entities from memory tags. Requires KORE_ENTITY_EXTRACTION=1."""
    from .integrations.entities import search_entities
    results = search_entities(agent_id, entity_type=type, limit=limit)
    return {"entities": results, "total": len(results)}


# ── Agents ────────────────────────────────────────────────────────────────────

@app.get("/agents")
def agents_list(_: str = _Auth) -> list[dict]:
    """List all agent IDs with memory count and last activity. No agent scoping — returns all agents."""
    return list_agents()


# ── Metrics ───────────────────────────────────────────────────────────────────

@app.get("/metrics", include_in_schema=False)
def metrics(agent_id: str | None = Query(None)) -> Response:
    """Prometheus-compatible metrics endpoint."""
    from .repository import get_stats
    stats = get_stats(agent_id)
    lines = [
        "# HELP kore_memories_total Total memory records",
        "# TYPE kore_memories_total gauge",
        f'kore_memories_total {stats["total_memories"]}',
        "# HELP kore_memories_active Active (non-decayed) memory records",
        "# TYPE kore_memories_active gauge",
        f'kore_memories_active {stats["active_memories"]}',
        "# HELP kore_memories_archived Archived memory records",
        "# TYPE kore_memories_archived gauge",
        f'kore_memories_archived {stats["archived_memories"]}',
        "# HELP kore_db_size_bytes Database file size in bytes",
        "# TYPE kore_db_size_bytes gauge",
        f'kore_db_size_bytes {stats["db_size_bytes"]}',
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; charset=utf-8")


# ── Audit log ────────────────────────────────────────────────────────────────

@app.get("/audit")
def audit_log(
    request: Request,
    event: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    since: str | None = Query(None, description="ISO datetime"),
    _: str = _Auth,
    agent_id: str = _Agent,
) -> dict:
    """Query the audit event log for the requesting agent."""
    from .audit import query_audit_log
    entries = query_audit_log(agent_id, event_type=event, limit=limit, since=since)
    return {"events": entries, "total": len(entries)}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request) -> HTMLResponse:
    """Dashboard web per gestione memorie. Richiede auth se non in local-only mode."""
    from .auth import _is_local, _local_only_mode
    if not (_local_only_mode() and _is_local(request)):
        # Non-local: richiede autenticazione
        await require_auth(request, request.headers.get("X-Kore-Key"))
    html = get_dashboard_html()
    # Inject CSP nonce into script tags
    nonce = getattr(request.state, "csp_nonce", "")
    html = html.replace("<script>", f'<script nonce="{nonce}">')
    return HTMLResponse(content=html)


# ── Utility ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> JSONResponse:
    from .repository import _embeddings_available
    return JSONResponse({
        "status": "ok",
        "version": app.version,
        "semantic_search": _embeddings_available(),
    })
