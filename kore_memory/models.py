"""
Kore — Pydantic models
Request/response schemas with validation.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "general",
    "project",
    "trading",
    "finance",
    "person",
    "preference",
    "task",
    "decision",
]


class MemorySaveRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "Il progetto usa FastAPI con SQLite per la persistenza",
                    "category": "project",
                    "importance": 4,
                },
                {
                    "content": "Riunione con il team alle 15:00",
                    "category": "task",
                },
            ]
        }
    }

    content: str = Field(..., min_length=3, max_length=4000)
    category: Category = Field("general")
    importance: int | None = Field(None, ge=1, le=5, description="None=auto-scored, 1-5=explicit")
    ttl_hours: int | None = Field(None, ge=1, le=8760, description="Time-to-live in ore (max 1 anno)")

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be blank")
        return v.strip()


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(None, min_length=3, max_length=4000)
    category: Category | None = None
    importance: int | None = Field(None, ge=1, le=5)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Content cannot be blank")
        return v.strip() if v else v


class MemoryRecord(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 42,
                    "content": "Il progetto usa FastAPI con SQLite",
                    "category": "project",
                    "importance": 4,
                    "decay_score": 0.95,
                    "created_at": "2026-01-15T10:30:00",
                    "updated_at": "2026-01-15T10:30:00",
                    "score": 3.8,
                }
            ]
        }
    }

    id: int
    content: str
    category: str
    importance: int
    decay_score: float = 1.0
    created_at: datetime
    updated_at: datetime
    score: float | None = None


class MemorySaveResponse(BaseModel):
    id: int
    importance: int
    message: str = "Memory saved"


class MemorySearchResponse(BaseModel):
    results: list[MemoryRecord]
    total: int
    cursor: str | None = Field(None, description="Opaque cursor for next page (base64)")
    has_more: bool = False
    # Deprecated fields kept for backwards compatibility
    offset: int = Field(0, deprecated=True, description="Deprecated: use cursor instead")


class MemoryImportRequest(BaseModel):
    memories: list[dict] = Field(..., min_length=1, max_length=500)


class MemoryImportResponse(BaseModel):
    imported: int
    message: str = "Import complete"


class MemoryExportResponse(BaseModel):
    memories: list[dict]
    total: int


class BatchSaveRequest(BaseModel):
    memories: list[MemorySaveRequest] = Field(..., min_length=1, max_length=100)


class BatchSaveResponse(BaseModel):
    saved: list[MemorySaveResponse]
    total: int


class TagRequest(BaseModel):
    tags: list[str] = Field(..., min_length=1, max_length=20)


class TagResponse(BaseModel):
    count: int
    tags: list[str] = []


class RelationRequest(BaseModel):
    target_id: int
    relation: str = Field("related", max_length=100)


class RelationResponse(BaseModel):
    relations: list[dict]
    total: int


class DecayRunResponse(BaseModel):
    updated: int
    message: str = "Decay pass complete"


class CleanupExpiredResponse(BaseModel):
    removed: int
    message: str = "Expired memories cleaned up"


class CompressRunResponse(BaseModel):
    clusters_found: int
    memories_merged: int
    new_records_created: int
    message: str = "Compression complete"


class ArchiveResponse(BaseModel):
    success: bool
    message: str = ""


class AutoTuneResponse(BaseModel):
    boosted: int
    reduced: int
    message: str = "Auto-tune complete"


class ScoringStatsResponse(BaseModel):
    total: int
    distribution: dict[str, int]  # importance level -> count
    avg_importance: float
    avg_access_count: float
    never_accessed_30d: int
    frequently_accessed: int


class SessionCreateRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    title: str | None = Field(None, max_length=500)


class SessionResponse(BaseModel):
    id: str
    agent_id: str
    title: str | None = None
    created_at: datetime
    ended_at: datetime | None = None
    memory_count: int = 0


class SessionSummaryResponse(BaseModel):
    session_id: str
    agent_id: str
    title: str | None = None
    created_at: str
    ended_at: str | None = None
    memory_count: int = 0
    categories: list[str] = []
    avg_importance: float = 0.0
    first_memory: str | None = None
    last_memory: str | None = None


class SessionDeleteResponse(BaseModel):
    success: bool
    unlinked_memories: int


class EntityRecord(BaseModel):
    type: str
    value: str
    memory_id: int
    tag: str


class EntityListResponse(BaseModel):
    entities: list[EntityRecord]
    total: int


class AgentRecord(BaseModel):
    agent_id: str
    memory_count: int
    last_active: str | None = None


class AgentListResponse(BaseModel):
    agents: list[AgentRecord]
    total: int


class AuditEventRecord(BaseModel):
    id: int
    event: str
    agent_id: str
    memory_id: int | None = None
    data: dict | str | None = None
    created_at: str


class AuditResponse(BaseModel):
    events: list[AuditEventRecord]
    total: int


# ── Graph RAG ────────────────────────────────────────────────────────────────


class GraphNodeRecord(BaseModel):
    id: int
    content: str
    category: str
    importance: int
    decay_score: float
    created_at: str
    hop: int


class GraphEdgeRecord(BaseModel):
    source_id: int
    target_id: int
    relation: str
    created_at: str


class GraphTraverseResponse(BaseModel):
    start: dict | None = None
    nodes: list[GraphNodeRecord] = []
    edges: list[GraphEdgeRecord] = []
    depth: int


# ── Summarization ────────────────────────────────────────────────────────────


class KeywordRecord(BaseModel):
    word: str
    score: float


class SummarizeResponse(BaseModel):
    topic: str
    memory_count: int
    keywords: list[KeywordRecord] = []
    categories: dict[str, int] = {}
    avg_importance: float = 0.0
    time_span: dict[str, str] | None = None


# ── ACL ──────────────────────────────────────────────────────────────────────


class ACLGrantRequest(BaseModel):
    target_agent: str = Field(..., min_length=1, max_length=64)
    permission: str = Field("read", pattern=r"^(read|write|admin)$")


class ACLRecord(BaseModel):
    agent_id: str
    permission: str
    granted_by: str
    created_at: str


class ACLResponse(BaseModel):
    success: bool
    permissions: list[ACLRecord] = []


class SharedMemoryRecord(BaseModel):
    id: int
    content: str
    category: str
    importance: int
    decay_score: float
    created_at: str
    updated_at: str
    owner_agent: str
    permission: str


class SharedMemoriesResponse(BaseModel):
    memories: list[SharedMemoryRecord]
    total: int


# ── Analytics ────────────────────────────────────────────────────────────────


class AnalyticsResponse(BaseModel):
    total_memories: int
    categories: dict[str, int]
    importance_distribution: dict[str, int]
    decay_analysis: dict[str, float | int]
    top_tags: list[dict]
    access_patterns: dict[str, float | int]
    growth_last_30d: list[dict]
    compressed_memories: int
    archived_memories: int
    total_relations: int


# ── GDPR ─────────────────────────────────────────────────────────────────────


class GDPRDeleteResponse(BaseModel):
    deleted_memories: int
    deleted_tags: int
    deleted_relations: int
    deleted_sessions: int
    deleted_events: int
    message: str = "All agent data permanently deleted"


# ── Plugins ──────────────────────────────────────────────────────────────────


class PluginListResponse(BaseModel):
    plugins: list[str]
    total: int
