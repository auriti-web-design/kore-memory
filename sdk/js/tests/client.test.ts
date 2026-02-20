/**
 * Tests for KoreClient
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { KoreClient } from "../src/client.js";
import {
  KoreAuthError,
  KoreNotFoundError,
  KoreValidationError,
} from "../src/errors.js";
import { mockResponse, mockFetch, mockFetchError } from "./helpers.js";

describe("KoreClient", () => {
  let client: KoreClient;
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    client = new KoreClient({
      baseUrl: "http://localhost:8765",
      agentId: "test-agent",
      apiKey: "test-key",
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe("Constructor", () => {
    it("should use default config", () => {
      const defaultClient = new KoreClient();
      expect(defaultClient).toBeDefined();
    });

    it("should strip trailing slash from baseUrl", () => {
      const clientWithSlash = new KoreClient({
        baseUrl: "http://localhost:8765/",
      });
      expect(clientWithSlash).toBeDefined();
    });
  });

  describe("save", () => {
    it("should save memory successfully", async () => {
      const mockResponseData = {
        id: 1,
        importance: 4,
        message: "Memory saved",
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.save({
        content: "Test memory",
        category: "general",
        importance: 4,
      });

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/save",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            "X-Agent-Id": "test-agent",
            "X-Kore-Key": "test-key",
          }),
          body: JSON.stringify({
            content: "Test memory",
            category: "general",
            importance: 4,
          }),
        })
      );
    });

    it("should handle validation error", async () => {
      mockFetch(mockResponse(422, { detail: "Content too short" }));

      await expect(
        client.save({ content: "ab" })
      ).rejects.toThrow(KoreValidationError);
    });
  });

  describe("saveBatch", () => {
    it("should save batch of memories", async () => {
      const mockResponseData = {
        saved: [
          { id: 1, importance: 3, message: "Memory saved" },
          { id: 2, importance: 4, message: "Memory saved" },
        ],
        total: 2,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const memories = [
        { content: "Memory 1", category: "project" as const },
        { content: "Memory 2", category: "task" as const },
      ];

      const result = await client.saveBatch(memories);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/save/batch",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ memories }),
        })
      );
    });
  });

  describe("search", () => {
    it("should search memories with all options", async () => {
      const mockResponseData = {
        results: [
          {
            id: 1,
            content: "Test memory",
            category: "general",
            importance: 3,
            decay_score: 0.95,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-01T00:00:00Z",
            score: 0.85,
          },
        ],
        total: 1,
        offset: 0,
        has_more: false,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.search({
        q: "test",
        limit: 10,
        offset: 0,
        category: "general",
        semantic: true,
      });

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/search?q=test&limit=10&offset=0&category=general&semantic=true",
        expect.objectContaining({
          method: "GET",
        })
      );
    });

    it("should search with minimal options", async () => {
      const mockResponseData = {
        results: [],
        total: 0,
        offset: 0,
        has_more: false,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.search({ q: "test" });

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/search?q=test",
        expect.objectContaining({
          method: "GET",
        })
      );
    });
  });

  describe("timeline", () => {
    it("should get timeline for subject", async () => {
      const mockResponseData = {
        results: [
          {
            id: 1,
            content: "Project started",
            category: "project",
            importance: 4,
            decay_score: 0.9,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
        offset: 0,
        has_more: false,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.timeline({
        subject: "project alpha",
        limit: 20,
      });

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/timeline?subject=project+alpha&limit=20",
        expect.objectContaining({
          method: "GET",
        })
      );
    });
  });

  describe("delete", () => {
    it("should delete memory successfully", async () => {
      mockFetch(mockResponse(204));

      const result = await client.delete(1);

      expect(result).toBe(true);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1",
        expect.objectContaining({
          method: "DELETE",
        })
      );
    });

    it("should handle not found error", async () => {
      mockFetch(mockResponse(404, { detail: "Memory not found" }));

      await expect(client.delete(999)).rejects.toThrow(KoreNotFoundError);
    });
  });

  describe("Tags", () => {
    it("should add tags to memory", async () => {
      const mockResponseData = {
        count: 2,
        tags: ["react", "frontend"],
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.addTags(1, ["react", "frontend"]);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1/tags",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ tags: ["react", "frontend"] }),
        })
      );
    });

    it("should get tags for memory", async () => {
      const mockResponseData = {
        count: 1,
        tags: ["react"],
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.getTags(1);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1/tags",
        expect.objectContaining({
          method: "GET",
        })
      );
    });

    it("should remove tags from memory", async () => {
      const mockResponseData = {
        count: 0,
        tags: [],
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.removeTags(1, ["old-tag"]);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1/tags",
        expect.objectContaining({
          method: "DELETE",
          body: JSON.stringify({ tags: ["old-tag"] }),
        })
      );
    });

    it("should search by tag", async () => {
      const mockResponseData = {
        results: [
          {
            id: 1,
            content: "React component",
            category: "project",
            importance: 3,
            decay_score: 0.9,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
        offset: 0,
        has_more: false,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.searchByTag("react", 10);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/tags/react/memories?limit=10",
        expect.objectContaining({
          method: "GET",
        })
      );
    });

    it("should encode tag in URL", async () => {
      mockFetch(mockResponse(200, { results: [], total: 0, offset: 0, has_more: false }));

      await client.searchByTag("tag with spaces");

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/tags/tag%20with%20spaces/memories",
        expect.anything()
      );
    });
  });

  describe("Relations", () => {
    it("should add relation between memories", async () => {
      const mockResponseData = {
        relations: [
          {
            source_id: 1,
            target_id: 2,
            relation: "depends_on",
            created_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.addRelation(1, 2, "depends_on");

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1/relations",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            target_id: 2,
            relation: "depends_on",
          }),
        })
      );
    });

    it("should add relation with default type", async () => {
      const mockResponseData = {
        relations: [],
        total: 0,
      };
      mockFetch(mockResponse(200, mockResponseData));

      await client.addRelation(1, 2);

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1/relations",
        expect.objectContaining({
          body: JSON.stringify({
            target_id: 2,
            relation: "related",
          }),
        })
      );
    });

    it("should get relations for memory", async () => {
      const mockResponseData = {
        relations: [
          {
            source_id: 1,
            target_id: 2,
            relation: "related",
            created_at: "2024-01-01T00:00:00Z",
          },
        ],
        total: 1,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.getRelations(1);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/memories/1/relations",
        expect.objectContaining({
          method: "GET",
        })
      );
    });
  });

  describe("Maintenance", () => {
    it("should run decay pass", async () => {
      const mockResponseData = {
        updated: 42,
        message: "Decay pass complete",
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.decayRun();

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/decay/run",
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("should run compression", async () => {
      const mockResponseData = {
        clusters_found: 3,
        memories_merged: 8,
        new_records_created: 3,
        message: "Compression complete",
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.compress();

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/compress",
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("should cleanup expired memories", async () => {
      const mockResponseData = {
        removed: 5,
        message: "Expired memories cleaned up",
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.cleanup();

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/cleanup",
        expect.objectContaining({
          method: "POST",
        })
      );
    });
  });

  describe("Backup", () => {
    it("should export memories", async () => {
      const mockResponseData = {
        memories: [
          {
            id: 1,
            content: "Test memory",
            category: "general",
            importance: 3,
          },
        ],
        total: 1,
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.exportMemories();

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/export",
        expect.objectContaining({
          method: "GET",
        })
      );
    });

    it("should import memories", async () => {
      const mockResponseData = {
        imported: 2,
        message: "Import complete",
      };
      mockFetch(mockResponse(200, mockResponseData));

      const memories = [
        { content: "Memory 1", category: "general" },
        { content: "Memory 2", category: "project" },
      ];

      const result = await client.importMemories(memories);

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/import",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ memories }),
        })
      );
    });
  });

  describe("Utility", () => {
    it("should get health status", async () => {
      const mockResponseData = {
        status: "healthy",
        version: "0.5.3",
        capabilities: {
          semantic_search: true,
          mcp_server: true,
        },
      };
      mockFetch(mockResponse(200, mockResponseData));

      const result = await client.health();

      expect(result).toEqual(mockResponseData);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/health",
        expect.objectContaining({
          method: "GET",
        })
      );
    });
  });

  describe("Error Handling", () => {
    it("should handle network error", async () => {
      mockFetchError(new Error("Network error"));

      await expect(
        client.save({ content: "test" })
      ).rejects.toThrow("Network error");
    });

    it("should handle auth error", async () => {
      mockFetch(mockResponse(401, { detail: "Invalid API key" }));

      await expect(
        client.save({ content: "test" })
      ).rejects.toThrow(KoreAuthError);
    });

    it("should handle malformed JSON error response", async () => {
      global.fetch = vi.fn().mockResolvedValue(
        new Response("invalid json", {
          status: 422,
          statusText: "Unprocessable Entity",
          headers: { "Content-Type": "application/json" },
        })
      );

      await expect(
        client.save({ content: "test" })
      ).rejects.toThrow();
    });
  });

  describe("Request Configuration", () => {
    it("should not include API key header when not provided", async () => {
      const clientWithoutKey = new KoreClient({
        baseUrl: "http://localhost:8765",
        agentId: "test-agent",
      });

      mockFetch(mockResponse(200, { id: 1, importance: 3, message: "saved" }));

      await clientWithoutKey.save({ content: "test" });

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.not.objectContaining({
            "X-Kore-Key": expect.any(String),
          }),
        })
      );
    });

    it("should handle undefined query parameters", async () => {
      mockFetch(mockResponse(200, { results: [], total: 0, offset: 0, has_more: false }));

      await client.search({
        q: "test",
        limit: undefined,
        category: undefined,
      });

      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:8765/search?q=test",
        expect.anything()
      );
    });
  });
});
