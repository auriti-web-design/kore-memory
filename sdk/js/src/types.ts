/**
 * Kore Memory - TypeScript Types
 * Mirrors src/models.py Pydantic models
 */

export type Category =
  | "general"
  | "project"
  | "trading"
  | "finance"
  | "person"
  | "preference"
  | "task"
  | "decision";

export interface MemorySaveRequest {
  content: string;
  category?: Category;
  importance?: number; // 1-5, 1=auto-scored
  ttl_hours?: number; // 1-8760
}

export interface MemoryUpdateRequest {
  content?: string;
  category?: Category;
  importance?: number; // 1-5
}

export interface MemoryRecord {
  id: number;
  content: string;
  category: string;
  importance: number;
  decay_score: number;
  created_at: string;
  updated_at: string;
  score?: number;
}

export interface MemorySaveResponse {
  id: number;
  importance: number;
  message: string;
}

export interface MemorySearchResponse {
  results: MemoryRecord[];
  total: number;
  offset: number;
  has_more: boolean;
  cursor?: string | null;
}

export interface BatchSaveRequest {
  memories: MemorySaveRequest[];
}

export interface BatchSaveResponse {
  saved: MemorySaveResponse[];
  total: number;
}

export interface TagRequest {
  tags: string[];
}

export interface TagResponse {
  count: number;
  tags: string[];
}

export interface RelationRequest {
  target_id: number;
  relation?: string;
}

export interface RelationRecord {
  source_id: number;
  target_id: number;
  relation: string;
  created_at: string;
}

export interface RelationResponse {
  relations: RelationRecord[];
  total: number;
}

export interface DecayRunResponse {
  updated: number;
  message: string;
}

export interface CompressRunResponse {
  clusters_found: number;
  memories_merged: number;
  new_records_created: number;
  message: string;
}

export interface CleanupExpiredResponse {
  removed: number;
  message: string;
}

export interface ArchiveResponse {
  success: boolean;
  message: string;
}

export interface MemoryExportResponse {
  memories: Record<string, any>[];
  total: number;
}

export interface MemoryImportRequest {
  memories: Record<string, any>[];
}

export interface MemoryImportResponse {
  imported: number;
  message: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  semantic_search: boolean;
  database: string;
}

// Client configuration
export interface KoreClientConfig {
  baseUrl?: string;
  apiKey?: string;
  agentId?: string;
  timeout?: number;
}

// Search options
export interface SearchOptions {
  q: string;
  limit?: number;
  offset?: number;
  category?: Category;
  semantic?: boolean;
  cursor?: string;
}

// Timeline options
export interface TimelineOptions {
  subject: string;
  limit?: number;
  offset?: number;
  cursor?: string;
}
