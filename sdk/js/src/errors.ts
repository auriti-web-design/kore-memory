/**
 * Kore Memory - Error Classes
 * Mirrors src/client.py error hierarchy
 */

export class KoreError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public detail?: any
  ) {
    super(message);
    this.name = "KoreError";
  }
}

export class KoreAuthError extends KoreError {
  constructor(message: string, statusCode?: number, detail?: any) {
    super(message, statusCode, detail);
    this.name = "KoreAuthError";
  }
}

export class KoreNotFoundError extends KoreError {
  constructor(message: string, statusCode?: number, detail?: any) {
    super(message, statusCode, detail);
    this.name = "KoreNotFoundError";
  }
}

export class KoreValidationError extends KoreError {
  constructor(message: string, statusCode?: number, detail?: any) {
    super(message, statusCode, detail);
    this.name = "KoreValidationError";
  }
}

export class KoreRateLimitError extends KoreError {
  constructor(message: string, statusCode?: number, detail?: any) {
    super(message, statusCode, detail);
    this.name = "KoreRateLimitError";
  }
}

export class KoreServerError extends KoreError {
  constructor(message: string, statusCode?: number, detail?: any) {
    super(message, statusCode, detail);
    this.name = "KoreServerError";
  }
}

/**
 * Maps HTTP status codes to appropriate Kore error classes
 */
export function mapHttpError(
  status: number,
  message: string,
  detail?: any
): KoreError {
  switch (status) {
    case 401:
    case 403:
      return new KoreAuthError(message, status, detail);
    case 404:
      return new KoreNotFoundError(message, status, detail);
    case 422:
      return new KoreValidationError(message, status, detail);
    case 429:
      return new KoreRateLimitError(message, status, detail);
    default:
      if (status >= 500) {
        return new KoreServerError(message, status, detail);
      }
      return new KoreError(message, status, detail);
  }
}
