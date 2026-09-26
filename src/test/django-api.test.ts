import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("../lib/backend", () => ({ isDjangoBackend: true }));
import { apiRequest } from "../lib/api";

const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

describe("Django API integration", () => {
  it("sends a student's selected academic level during registration", async () => {
    const fetch = vi.fn().mockResolvedValue(response({ data: { user: { id: "user-1" } } }, 201));
    vi.stubGlobal("fetch", fetch);

    await apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: "ada@example.edu",
        password: "StrongPass123!",
        identifier: "SWE/2026/001",
        firstName: "Ada",
        lastName: "Test",
        phone: "",
        memberType: "Student",
        level: "600",
        acceptedPolicies: true,
      }),
    });

    const [, init] = fetch.mock.calls[0]!;
    expect(JSON.parse(init.body)).toMatchObject({
      matric_no: "SWE/2026/001",
      community: "STUDENT",
      academic_level: "600",
    });
  });

  it.each([
    ["Staff", "staff@example.edu.ng", "STAFF"],
    ["Guest", "guest@example.com", "GUEST"],
  ])("registers a %s with email only", async (memberType, email, community) => {
    const fetch = vi.fn().mockResolvedValue(response({ data: { user: { id: "user-1" } } }, 201));
    vi.stubGlobal("fetch", fetch);

    await apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password: "StrongPass123!",
        firstName: "Email",
        lastName: "Only",
        phone: "",
        memberType,
        acceptedPolicies: true,
      }),
    });

    const [, init] = fetch.mock.calls[0]!;
    const payload = JSON.parse(init.body);
    expect(payload).toMatchObject({ email, community });
    expect(payload).not.toHaveProperty("matric_no");
    expect(payload).not.toHaveProperty("academic_level");
  });

  it("maps a staff account to the limited account experience", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      data: {
        id: "staff-1",
        role: "MEMBER",
        first_name: "Tolu",
        last_name: "Staff",
        email: "tolu@example.edu.ng",
        community: "STAFF",
      },
    })));

    await expect(apiRequest("/auth/me")).resolves.toMatchObject({
      data: { role: "member", community: "staff" },
    });
  });

  it("maps Django sessions to the account security view model", async () => {
    const fetch = vi.fn().mockResolvedValue(response({ data: [
      { jti: "session-1", created_at: "2026-09-24T10:00:00Z", expires_at: "2026-10-24T10:00:00Z", is_current: true },
      { jti: "session-2", created_at: "2026-09-23T10:00:00Z", expires_at: "2026-10-23T10:00:00Z", is_current: false },
    ] }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/auth/sessions")).resolves.toMatchObject({
      data: [
        { id: "session-1", device: "Signed-in device", lastActiveAt: "2026-09-24T10:00:00Z", current: true },
        { id: "session-2", device: "Signed-in device", lastActiveAt: "2026-09-23T10:00:00Z", current: false },
      ],
    });
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/auth/sessions/");
  });

  it("derives the current chapel session and joins its attendance records", async () => {
    const now = Date.now();
    const opensAt = new Date(now - 60_000).toISOString();
    const closesAt = new Date(now + 3_600_000).toISOString();
    const fetch = vi.fn()
      .mockResolvedValueOnce(response({ data: [{ id: "session-1", branch: "branch-1", label: "Sunday service", venue: "Chapel", is_open: true, state: "OPEN", opened_at: opensAt, window_opens_at: opensAt, window_closes_at: closesAt, record_count: 1 }] }))
      .mockResolvedValueOnce(response({ data: [{ id: "member-1", full_name: "Ada Okafor", email: "ada@example.edu", matric_no: "CU/26/101" }] }))
      .mockResolvedValueOnce(response({ data: [{ id: "record-1", member: "member-1", method: "QR_CODE", status: "PRESENT", checked_in_at: opensAt }] }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/attendance/sessions/current?branch=branch-1")).resolves.toMatchObject({
      data: {
        session: { id: "session-1", title: "Sunday service", venue: "Chapel", status: "open", count: 1 },
        records: [{ id: "record-1", memberName: "Ada Okafor", method: "qr", status: "present" }],
      },
    });
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/attendance/sessions/?branch=branch-1&page_size=100",
      "/api/v1/members/?branch=branch-1&page_size=100",
      "/api/v1/attendance/records/?session=session-1&page_size=100",
    ]);
  });

  it("includes venue when listing attendance sessions", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: [{
        id: "session-3",
        label: "Midweek Service",
        venue: "Marquee",
        is_open: true,
        state: "OPEN",
        opened_at: "2026-09-24T08:00:00Z",
        window_opens_at: "2026-09-24T08:00:00Z",
        window_closes_at: "2026-09-24T09:00:00Z",
      }],
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/attendance/sessions?branch=branch-1")).resolves.toMatchObject({
      data: [{ id: "session-3", title: "Midweek Service", venue: "Marquee" }],
    });
  });

  it("maps attendance creation and correction to Django fields and methods", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(response({ data: { id: "session-2" } }, 201))
      .mockResolvedValueOnce(response({ data: { id: "record-1" } }));
    vi.stubGlobal("fetch", fetch);
    const date = "2026-10-04";

    await apiRequest("/attendance/sessions", {
      method: "POST",
      body: JSON.stringify({ title: "Sunday service", date, opensAt: "09:00", closesAt: "11:00", branchId: "branch-1", venue: "Marquee" }),
    });
    await apiRequest("/attendance/records/record-1", {
      method: "PATCH",
      body: JSON.stringify({ status: "LATE", reason: "Verified against the usher register." }),
    });

    const expectedOpen = new Date(`${date}T09:00`).toISOString();
    const expectedClose = new Date(`${date}T11:00`).toISOString();
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/attendance/sessions/");
    expect(JSON.parse(fetch.mock.calls[0]?.[1].body)).toEqual({
      branch: "branch-1",
      label: "Sunday service",
      venue: "Marquee",
      window_opens_at: expectedOpen,
      window_closes_at: expectedClose,
    });
    expect(fetch.mock.calls[1]?.[0]).toBe("/api/v1/attendance/records/record-1/correct/");
    expect(fetch.mock.calls[1]?.[1]).toMatchObject({ method: "POST", body: JSON.stringify({ status: "LATE", reason: "Verified against the usher register." }) });
  });

  it("shows backend validation details when attendance session creation fails", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      success: false,
      message: "Validation failed.",
      errors: { venue: ["This field is required."] },
    }, 400));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/attendance/sessions", {
      method: "POST",
      body: JSON.stringify({
        title: "Sunday service",
        date: "2026-10-04",
        opensAt: "09:00",
        closesAt: "11:00",
        branchId: "branch-1",
        venue: "",
      }),
    })).rejects.toMatchObject({
      message: "Validation failed. venue: This field is required.",
      fieldErrors: { venue: ["This field is required."] },
      status: 400,
    });

    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/attendance/sessions/");
    expect(JSON.parse(fetch.mock.calls[0]?.[1].body)).toMatchObject({ branch: "branch-1", venue: "" });
  });

  it("uses the real JWT login endpoint without sending credentials to browser-only routes", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: { user: { id: "user-1", role: "MEMBER", first_name: "Ada", last_name: "Test", email: "ada@example.edu", effective_permissions: ["events.view"] } },
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/auth/login", { method: "POST", body: JSON.stringify({ identifier: "SWE/2024/005", password: "secret" }) }))
      .resolves.toMatchObject({ data: { id: "user-1", role: "member", name: "Ada Test", permissions: ["dashboard:view", "events:read"] } });

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

  it("keeps legacy Unit Leader accounts in the Unit Leader workspace", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      data: {
        id: "legacy-unit-leader",
        role: "UNIT_LEADER",
        first_name: "Legacy",
        last_name: "Leader",
      },
    })));

    await expect(apiRequest("/auth/me")).resolves.toMatchObject({
      data: { role: "unit_leader" },
    });
  });

  it("grants the inventory route only when Django confirms the Protocol inventory assignment", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      data: {
        id: "protocol-leader",
        role: "UNIT_HEAD",
        first_name: "Tomi",
        last_name: "Protocol",
        inventory_access: true,
      },
    })));

    await expect(apiRequest("/auth/me")).resolves.toMatchObject({
      data: { role: "unit_leader", permissions: expect.arrayContaining(["assets:read", "assets:write"]) },
    });
  });

  it("grants media publishing only when Django confirms the approved media assignment", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      data: {
        id: "media-leader",
        role: "UNIT_HEAD",
        first_name: "Mira",
        last_name: "Media",
        media_access: true,
      },
    })));

    await expect(apiRequest("/auth/me")).resolves.toMatchObject({
      data: { role: "unit_leader", permissions: expect.arrayContaining(["media:write"]) },
    });
  });

  it("sends device uploads as multipart requests to the Django endpoints", async () => {
    const fetch = vi.fn().mockResolvedValue(response({ data: { file_url: "https://files.example/photo.jpg" } }, 201));
    fetch.mockResolvedValueOnce(response({ data: { photo_url: "https://files.example/photo.jpg" } }, 201));
    vi.stubGlobal("fetch", fetch);
    const photo = new File(["image"], "photo.jpg", { type: "image/jpeg" });
    const payload = new FormData();
    payload.set("file", photo);

    await apiRequest("/account/profile/photo", { method: "POST", body: payload });
    await apiRequest("/uploads", { method: "POST", body: payload });

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/auth/profile/photo/",
      "/api/v1/uploads/upload/",
    ]);
    expect(fetch.mock.calls[0]?.[1].headers.get("Content-Type")).toBeNull();
  });

  it("loads the admin dashboard for administrator sessions", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: {
        members: { total_members: 42, active_members: 38 },
        events: { upcoming_events: 3 },
      },
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/dashboard?role=super_admin")).resolves.toMatchObject({
      data: {
        metrics: [
          { label: "members total members", value: "42" },
          { label: "members active members", value: "38" },
          { label: "events upcoming events", value: "3" },
        ],
      },
    });
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/dashboard/admin/");
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

  it.each([
    ["/worker-assignments", "/api/v1/operations/workers/?page=1"],
    ["/finance/transactions", "/api/v1/operations/finance/?page=1"],
    ["/communications/broadcasts", "/api/v1/operations/communication/?page=1"],
    ["/assets", "/api/v1/operations/assets/?page=1"],
    ["/media", "/api/v1/operations/media/?page=1"],
    ["/cms/content", "/api/v1/operations/cms/?page=1"],
  ])("connects the %s operations page to Django", async (frontendPath, djangoPath) => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: [{ id: "record-1", primary: "Record", secondary: "Branch", detail: "Details", status: "ACTIVE" }],
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest(`${frontendPath}?page=1`)).resolves.toMatchObject({
      data: [{ id: "record-1", primary: "Record", status: "ACTIVE" }],
    });
    expect(fetch.mock.calls[0]?.[0]).toBe(djangoPath);
  });

  it("connects analytics, audit, privacy, and operation actions to Django", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(response({ data: [] })));
    vi.stubGlobal("fetch", fetch);

    await apiRequest("/analytics/overview?page=1");
    await apiRequest("/audit-events?page=1");
    await apiRequest("/account/data-export-requests", { method: "POST", body: "{}" });
    await apiRequest("/assets/asset-1/movements", {
      method: "POST", body: JSON.stringify({ action: "issue" }),
    });

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/analytics/overview/?page=1",
      "/api/v1/audit/logs/?page=1",
      "/api/v1/account/data-export-requests/",
      "/api/v1/operations/assets/asset-1/movement/",
    ]);
  });

  it("maps inventory readiness alerts from the protected Django endpoint", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: {
        low_stock: [{ id: "asset-1", primary: "Communion cups", status: "LOW_STOCK", quantity_on_hand: 2, reorder_level: 12 }],
        maintenance_due: [{ id: "maintenance-1", asset: "asset-2", title: "Service speaker", details: "Annual check", due_at: "2026-09-19", status: "SCHEDULED" }],
      },
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/assets/alerts")).resolves.toMatchObject({
      data: {
        lowStock: [{ id: "asset-1", quantityOnHand: 2, lowStock: false }],
        maintenanceDue: [{ id: "maintenance-1", assetId: "asset-2", dueAt: "2026-09-19" }],
      },
    });
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/operations/assets/alerts/");
  });

  it("maps protected inventory history to the register view", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: {
        movements: [{ id: "movement-1", movement_type: "ISSUE", quantity_change: -1, quantity_after: 4, reason: "Sunday service", created_at: "2026-09-19T10:00:00Z" }],
        maintenance: [{ id: "maintenance-1", title: "Speaker service", due_at: "2026-09-20", status: "SCHEDULED", completed_at: null }],
      },
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/assets/asset-1/history")).resolves.toMatchObject({
      data: {
        movements: [{ type: "ISSUE", quantityChange: -1, quantityAfter: 4 }],
        maintenance: [{ dueAt: "2026-09-20", completedAt: null }],
      },
    });
    expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/operations/assets/asset-1/history/");
  });

  it("passes public media searches and gallery details to Django", async () => {
    const fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(response({ data: { sections: [] } })),
    );
    vi.stubGlobal("fetch", fetch);

    await apiRequest("/public/content/sermons?search=faith");
    await apiRequest("/public/gallery/welcome-service");

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/public/content/sermons/?search=faith",
      "/api/v1/public/gallery/welcome-service/",
    ]);
  });

  it("maps the editorial review workflow to Django", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      data: {
        id: "content-1",
        primary: "Sunday message",
        secondary: "Sermon",
        detail: "A published message",
        status: "IN_REVIEW",
        content_type: "SERMON",
      },
    }));
    vi.stubGlobal("fetch", fetch);

    await expect(
      apiRequest("/cms/content/content-1/submit", {
        method: "POST",
        body: "{}",
      }),
    ).resolves.toMatchObject({
      data: { id: "content-1", status: "IN_REVIEW", contentType: "SERMON" },
    });
    expect(fetch.mock.calls[0]?.[0]).toBe(
      "/api/v1/operations/cms/content-1/submit/",
    );
  });

  it("connects testimony moderation and private community resources to Django", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(response({ data: { id: "testimony-1", title: "Answered prayer", details: "Details", consent_to_publish: true, status: "PENDING", created_at: "2026-09-19T10:00:00Z" } }, 201))
      .mockResolvedValueOnce(response({ data: [{ id: "resource-1", title: "Study guide", url: "https://example.edu/guide", description: "Week one", created_at: "2026-09-19T10:00:00Z", created_by_name: "Leader" }] }));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/care/testimonies", {
      method: "POST",
      body: JSON.stringify({ title: "Answered prayer", details: "Details", consentToPublish: true }),
    })).resolves.toMatchObject({ data: { consentToPublish: true, status: "PENDING" } });
    await expect(apiRequest("/communities/group-1/resources")).resolves.toMatchObject({
      data: [{ title: "Study guide" }],
    });

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/prayer/testimonies/",
      "/api/v1/community-memberships/group-1/resources/",
    ]);
    expect(JSON.parse(fetch.mock.calls[0]?.[1].body)).toEqual({
      title: "Answered prayer", details: "Details", consent_to_publish: true,
    });
  });
});
