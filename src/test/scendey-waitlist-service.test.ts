import { afterEach, describe, expect, it, vi } from "vitest";
import { scendeyWaitlistService, ScendeyWaitlistRequestError } from "../features/scendey-waitlist-service";

afterEach(() => vi.unstubAllGlobals());

describe("Scendey waitlist HTTP client", () => {
  it("submits only to the ChapelFlow server route with an explicit consent value", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: { processed: true, message: "Processed" },
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await scendeyWaitlistService.join({
      name: "Test Visitor",
      email: "visitor@example.com",
      audienceCategory: "student",
      marketingConsent: false,
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/public/scendey-waitlist/", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({
        name: "Test Visitor",
        email: "visitor@example.com",
        audienceCategory: "student",
        marketingConsent: false,
      }),
    }));
  });

  it("preserves server validation messages and HTTP status for retry messaging", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ message: "Check the highlighted fields." }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    )));
    await expect(scendeyWaitlistService.join({
      name: "Visitor",
      email: "bad@example.com",
      audienceCategory: "business",
      marketingConsent: false,
    })).rejects.toMatchObject({ status: 400, message: "Check the highlighted fields." });
  });

  it("handles network failures without pretending the signup was sent", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(scendeyWaitlistService.join({
      name: "Visitor",
      email: "visitor@example.com",
      audienceCategory: "other",
      marketingConsent: false,
    })).rejects.toBeInstanceOf(ScendeyWaitlistRequestError);
  });
});
