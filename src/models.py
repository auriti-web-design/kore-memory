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
    content: str = Field(..., min_length=3, max_length=4000)
    category: Category = Field("general")
    importance: int = Field(1, ge=1, le=5, description="1=auto-scored, 2-5=explicit")
    ttl_hours: int | None = Field(None, ge=1, le=8760, description="Time-to-live in ore (max 1 anno)")

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be blank")
        return v.strip()


class MemoryRecord(BaseModel):
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
    offset: int = 0
    has_more: bool = False


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
