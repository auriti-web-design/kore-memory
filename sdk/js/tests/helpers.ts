/**
 * Test helpers for mocking fetch responses
 */

export function mockResponse(
  status: number,
  body?: any,
  headers?: Record<string, string>
): Response {
  const responseBody = body !== undefined ? JSON.stringify(body) : undefined;
  
  return new Response(responseBody, {
    status,
    statusText: getStatusText(status),
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  });
}

export function mockFetch(response: Response): void {
  global.fetch = vi.fn().mockResolvedValue(response);
}

export function mockFetchError(error: Error): void {
  global.fetch = vi.fn().mockRejectedValue(error);
}

function getStatusText(status: number): string {
  const statusTexts: Record<number, string> = {
    200: "OK",
    201: "Created",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
  };
  return statusTexts[status] || "Unknown";
}
