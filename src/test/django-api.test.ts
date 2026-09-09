import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("../lib/backend", () => ({ isDjangoBackend: true }));
import { apiRequest } from "../lib/api";

const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

describe("Django API integration", () => {
  it("uses the real JWT login endpoint without sending credentials to browser-only routes", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: { user: { id: "user-1", role: "MEMBER", first_name: "Ada", last_name: "Test", email: "ada@example.edu" } },
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/auth/login", { method: "POST", body: JSON.stringify({ identifier: "SWE/2024/005", password: "secret" }) }))
      .resolves.toMatchObject({ data: { id: "user-1", role: "member", name: "Ada Test" } });

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toBe("/api/v1/auth/login/");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ matric_no: "SWE/2024/005", password: "secret" });
  });

  it("maps Django pagination, filters, and member fields", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: [{ id: "m1", full_name: "Ada Test", membership_status: "ACTIVE" }],
      pagination: { count: 42, current_page: 2, page_size: 10 },
    }));
    vi.stubGlobal("fetch", fetch);
    await expect(apiRequest("/members?page=2&pageSize=10&status=active")).resolves.toMatchObject({
      total: 42, page: 2, pageSize: 10, data: [{ name: "Ada Test", status: "active" }],
    });
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/members/?page=2&page_size=10&membership_status=ACTIVE");
  });

  it("normalizes backend validation errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ message: "Validation failed.", errors: { email: ["Already registered"] } }, 400)));
    await expect(apiRequest("/auth/login", { method: "POST", body: "{}" })).rejects.toMatchObject({
      status: 400, fieldErrors: { email: ["Already registered"] },
    });
  });

  it("renews an expired access cookie before treating a Django session as signed out", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(response({ detail: "Token is invalid" }, 401))
      .mockResolvedValueOnce(response({ data: {} }))
      .mockResolvedValueOnce(response({
        data: { id: "user-1", role: "MEMBER", first_name: "Ada", last_name: "Test" },
      }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/auth/me")).resolves.toMatchObject({ data: { id: "user-1" } });
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/auth/me/",
      "/api/v1/auth/refresh/",
      "/api/v1/auth/me/",
    ]);
  });

  it("does not send unsupported operations to unrelated endpoints", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(apiRequest("/members", { method: "POST", body: "{}" })).rejects.toMatchObject({ code: "UNSUPPORTED_OPERATION" });
    expect(fetch).not.toHaveBeenCalled();
  });
});
