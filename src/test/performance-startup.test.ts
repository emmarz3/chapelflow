import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

beforeEach(() => {
  document.cookie = "chapelflow_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  localStorage.removeItem("chapelflow:session-established");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authentication startup performance", () => {
  it("does not request refresh for an anonymous current-user check", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ detail: "Unauthenticated." }, 401),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/auth/me")).rejects.toMatchObject({ status: 401 });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/v1/auth/me/");
  });

  it("still refreshes an expired access cookie when a prior session is known", async () => {
    localStorage.setItem("chapelflow:session-established", "1");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Expired access token." }, 401))
      .mockResolvedValueOnce(jsonResponse({ data: { csrf_token: "rotated-csrf" } }))
      .mockResolvedValueOnce(jsonResponse({
        data: {
          id: "member-1",
          email: "student@example.edu.ng",
          first_name: "Ada",
          last_name: "Okafor",
          role: "MEMBER",
          community: "STUDENT",
          effective_permissions: [],
        },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/auth/me")).resolves.toMatchObject({
      data: { id: "member-1" },
    });

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/api/v1/auth/me/",
      "/api/v1/auth/refresh/",
      "/api/v1/auth/me/",
    ]);
  });

  it("tries refresh for a protected app session even before the session hint exists", async () => {
    window.history.replaceState({}, "", "/app");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "Expired access token." }, 401))
      .mockResolvedValueOnce(jsonResponse({ data: { csrf_token: "rotated-csrf" } }))
      .mockResolvedValueOnce(jsonResponse({
        data: {
          id: "legacy-member",
          email: "legacy@example.edu.ng",
          first_name: "Legacy",
          last_name: "Member",
          role: "MEMBER",
          community: "STUDENT",
          effective_permissions: [],
        },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/auth/me")).resolves.toMatchObject({
      data: { id: "legacy-member" },
    });
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/api/v1/auth/me/",
      "/api/v1/auth/refresh/",
      "/api/v1/auth/me/",
    ]);
  });

  it("establishes CSRF before the first login mutation", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ data: { csrf_token: "initial-csrf" } }))
      .mockResolvedValueOnce(jsonResponse({
        data: {
          user: {
            id: "member-1",
            email: "student@example.edu.ng",
            first_name: "Ada",
            last_name: "Okafor",
            role: "MEMBER",
            community: "STUDENT",
            effective_permissions: [],
          },
        },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.post("/auth/login", {
      identifier: "student@example.edu.ng",
      password: "StrongPass123!",
    })).resolves.toMatchObject({ data: { id: "member-1" } });

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/api/v1/auth/csrf/",
      "/api/v1/auth/login/",
    ]);
    const loginInit = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(new Headers(loginInit.headers).get("X-ChapelFlow-CSRF")).toBe("initial-csrf");
    expect(localStorage.getItem("chapelflow:session-established")).toBe("1");
  });
});
