import type { ApiErrorShape } from "../types/domain";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api"
).replace(/\/$/, "");

export class ApiError extends Error implements ApiErrorShape {
  code: string;
  fieldErrors?: Record<string, string[]>;
  requestId?: string;
  status: number;
  constructor(error: ApiErrorShape) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.fieldErrors = error.fieldErrors;
    this.requestId = error.requestId;
    this.status = error.status;
  }
}

function safeRedirect(value: string | null) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/app";
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      signal: init.signal ?? controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        ...init.headers,
      },
    });
    if (
      response.status === 401 &&
      window.location.pathname.startsWith("/app")
    ) {
      window.location.assign(
        `/login?returnTo=${encodeURIComponent(safeRedirect(window.location.pathname))}&reason=expired`,
      );
      throw new ApiError({
        code: "SESSION_EXPIRED",
        message: "Your session has expired.",
        status: 401,
      });
    }
    if (!response.ok) {
      const fallback = {
        code: "REQUEST_FAILED",
        message: "We could not complete that request.",
        status: response.status,
      };
      let body: Partial<ApiErrorShape> = {};
      try {
        body = (await response.json()) as Partial<ApiErrorShape>;
      } catch {
        /* Non-JSON responses use the safe fallback. */
      }
      throw new ApiError({ ...fallback, ...body, status: response.status });
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError")
      throw new ApiError({
        code: "TIMEOUT",
        message: "The request took too long. Please try again.",
        status: 408,
      });
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "Check your internet connection and try again.",
      status: 0,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) =>
    apiRequest<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body: unknown) =>
    apiRequest<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
};
