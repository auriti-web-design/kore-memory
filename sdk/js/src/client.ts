/**
 * Kore Memory - JavaScript/TypeScript Client
 * Mirrors src/client.py functionality
 */

import { mapHttpError } from "./errors.js";
import type {
  BatchSaveRequest,
  BatchSaveResponse,
  CleanupExpiredResponse,
  CompressRunResponse,
  DecayRunResponse,
  HealthResponse,
  KoreClientConfig,
  MemoryExportResponse,
  MemoryImportRequest,
  MemoryImportResponse,
  MemoryRecord,
  MemorySaveRequest,
  MemorySaveResponse,
  MemorySearchResponse,
  RelationResponse,
  SearchOptions,
  TagResponse,
  TimelineOptions,
} from "./types.js";

export class KoreClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly agentId: string;
  private readonly timeout: number;

  constructor(config: KoreClientConfig = {}) {
    this.baseUrl = config.baseUrl?.replace(/\/$/, "") || "http://localhost:8765";
    this.apiKey = config.apiKey;
    this.agentId = config.agentId || "default";
    this.timeout = config.timeout || 30000;
  }

  private async _request<T>(
    method: string,
    path: string,
    body?: any,
    params?: Record<string, string | number | boolean>
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    const headers: Record<string, string> = {
      "X-Agent-Id": this.agentId,
    };

    if (this.apiKey) {
      headers["X-Kore-Key"] = this.apiKey;
    }

    if (body) {
      headers["Content-Type"] = "application/json";
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorDetail;
        try {
          errorDetail = await response.json();
        } catch {
          errorDetail = await response.text();
        }
        
        const message = typeof errorDetail === "object" && errorDetail.detail
          ? errorDetail.detail
          : String(errorDetail || response.statusText);
        
        throw mapHttpError(response.status, message, errorDetail);
      }

      // Handle 204 No Content (DELETE responses)
      if (response.status === 204) {
        return true as T;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);
      if (error.name === "AbortError") {
        throw new Error(`Request timeout after ${this.timeout}ms`);
      }
      throw error;
    }
  }

  // Core memory operations
  async save(input: MemorySaveRequest): Promise<MemorySaveResponse> {
    return this._request<MemorySaveResponse>("POST", "/save", input);
  }

  async saveBatch(memories: MemorySaveRequest[]): Promise<BatchSaveResponse> {
    const body: BatchSaveRequest = { memories };
    return this._request<BatchSaveResponse>("POST", "/save/batch", body);
  }

  async search(options: SearchOptions): Promise<MemorySearchResponse> {
    const { q, ...params } = options;
    return this._request<MemorySearchResponse>("GET", "/search", undefined, {
      q,
      ...params,
    });
  }

  async timeline(options: TimelineOptions): Promise<MemorySearchResponse> {
    const { subject, ...params } = options;
    return this._request<MemorySearchResponse>("GET", "/timeline", undefined, {
      subject,
      ...params,
    });
  }

  async delete(memoryId: number): Promise<boolean> {
    return this._request<boolean>("DELETE", `/memories/${memoryId}`);
  }

  // Tags
  async addTags(memoryId: number, tags: string[]): Promise<TagResponse> {
    return this._request<TagResponse>("POST", `/memories/${memoryId}/tags`, {
      tags,
    });
  }

  async getTags(memoryId: number): Promise<TagResponse> {
    return this._request<TagResponse>("GET", `/memories/${memoryId}/tags`);
  }

  async removeTags(memoryId: number, tags: string[]): Promise<TagResponse> {
    return this._request<TagResponse>("DELETE", `/memories/${memoryId}/tags`, {
      tags,
    });
  }

  async searchByTag(tag: string, limit?: number): Promise<MemorySearchResponse> {
    return this._request<MemorySearchResponse>(
      "GET",
      `/tags/${encodeURIComponent(tag)}/memories`,
      undefined,
      limit ? { limit } : undefined
    );
  }

  // Relations
  async addRelation(
    memoryId: number,
    targetId: number,
    relation = "related"
  ): Promise<RelationResponse> {
    return this._request<RelationResponse>(
      "POST",
      `/memories/${memoryId}/relations`,
      { target_id: targetId, relation }
    );
  }

  async getRelations(memoryId: number): Promise<RelationResponse> {
    return this._request<RelationResponse>(
      "GET",
      `/memories/${memoryId}/relations`
    );
  }

  // Maintenance
  async decayRun(): Promise<DecayRunResponse> {
    return this._request<DecayRunResponse>("POST", "/decay/run");
  }

  async compress(): Promise<CompressRunResponse> {
    return this._request<CompressRunResponse>("POST", "/compress");
  }

  async cleanup(): Promise<CleanupExpiredResponse> {
    return this._request<CleanupExpiredResponse>("POST", "/cleanup");
  }

  // Backup
  async exportMemories(): Promise<MemoryExportResponse> {
    return this._request<MemoryExportResponse>("GET", "/export");
  }

  async importMemories(
    memories: Record<string, any>[]
  ): Promise<MemoryImportResponse> {
    const body: MemoryImportRequest = { memories };
    return this._request<MemoryImportResponse>("POST", "/import", body);
  }

  // Utility
  async health(): Promise<HealthResponse> {
    return this._request<HealthResponse>("GET", "/health");
  }
}
