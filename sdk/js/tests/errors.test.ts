/**
 * Tests for error mapping and hierarchy
 */

import { describe, it, expect } from "vitest";
import {
  KoreError,
  KoreAuthError,
  KoreNotFoundError,
  KoreValidationError,
  KoreRateLimitError,
  KoreServerError,
  mapHttpError,
} from "../src/errors.js";

describe("Error Classes", () => {
  it("should create base KoreError", () => {
    const error = new KoreError("Test error", 400, { field: "invalid" });
    expect(error.name).toBe("KoreError");
    expect(error.message).toBe("Test error");
    expect(error.statusCode).toBe(400);
    expect(error.detail).toEqual({ field: "invalid" });
    expect(error instanceof Error).toBe(true);
  });

  it("should create KoreAuthError", () => {
    const error = new KoreAuthError("Unauthorized", 401);
    expect(error.name).toBe("KoreAuthError");
    expect(error instanceof KoreError).toBe(true);
    expect(error instanceof Error).toBe(true);
  });

  it("should create KoreNotFoundError", () => {
    const error = new KoreNotFoundError("Not found", 404);
    expect(error.name).toBe("KoreNotFoundError");
    expect(error instanceof KoreError).toBe(true);
  });

  it("should create KoreValidationError", () => {
    const error = new KoreValidationError("Validation failed", 422);
    expect(error.name).toBe("KoreValidationError");
    expect(error instanceof KoreError).toBe(true);
  });

  it("should create KoreRateLimitError", () => {
    const error = new KoreRateLimitError("Rate limited", 429);
    expect(error.name).toBe("KoreRateLimitError");
    expect(error instanceof KoreError).toBe(true);
  });

  it("should create KoreServerError", () => {
    const error = new KoreServerError("Server error", 500);
    expect(error.name).toBe("KoreServerError");
    expect(error instanceof KoreError).toBe(true);
  });
});

describe("mapHttpError", () => {
  it("should map 401 to KoreAuthError", () => {
    const error = mapHttpError(401, "Unauthorized");
    expect(error instanceof KoreAuthError).toBe(true);
    expect(error.statusCode).toBe(401);
  });

  it("should map 403 to KoreAuthError", () => {
    const error = mapHttpError(403, "Forbidden");
    expect(error instanceof KoreAuthError).toBe(true);
  });

  it("should map 404 to KoreNotFoundError", () => {
    const error = mapHttpError(404, "Not found");
    expect(error instanceof KoreNotFoundError).toBe(true);
  });

  it("should map 422 to KoreValidationError", () => {
    const error = mapHttpError(422, "Validation error");
    expect(error instanceof KoreValidationError).toBe(true);
  });

  it("should map 429 to KoreRateLimitError", () => {
    const error = mapHttpError(429, "Rate limited");
    expect(error instanceof KoreRateLimitError).toBe(true);
  });

  it("should map 500 to KoreServerError", () => {
    const error = mapHttpError(500, "Server error");
    expect(error instanceof KoreServerError).toBe(true);
  });

  it("should map 502 to KoreServerError", () => {
    const error = mapHttpError(502, "Bad gateway");
    expect(error instanceof KoreServerError).toBe(true);
  });

  it("should map unknown status to KoreError", () => {
    const error = mapHttpError(418, "I'm a teapot");
    expect(error instanceof KoreError).toBe(true);
    expect(error instanceof KoreAuthError).toBe(false);
    expect(error.statusCode).toBe(418);
  });

  it("should preserve detail in mapped error", () => {
    const detail = { field: "content", message: "too short" };
    const error = mapHttpError(422, "Validation failed", detail);
    expect(error.detail).toEqual(detail);
  });
});
