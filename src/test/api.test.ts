import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("API error normalization", () => {
  it("preserves safe backend validation details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "VALIDATION_ERROR",
            message: "Check the highlighted fields.",
            fieldErrors: { email: ["Invalid email"] },
            requestId: "req-123",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    await expect(
      apiRequest("/members", { method: "POST" }),
    ).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
      status: 422,
      requestId: "req-123",
      fieldErrors: { email: ["Invalid email"] },
    } satisfies Partial<ApiError>);
  });

  it("uses a generic message for non-JSON server failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Proxy failure", { status: 502 })),
    );
    await expect(apiRequest("/dashboard")).rejects.toMatchObject({
      code: "REQUEST_FAILED",
      message: "We could not complete that request.",
      status: 502,
    });
  });

  it("sends requests with cookie credentials instead of browser-stored tokens", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await apiRequest("/auth/me");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/me"),
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
