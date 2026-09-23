import { afterEach, describe, expect, it, vi } from "vitest";
import {
  attendanceService,
  eventService,
  memberService,
  operationsService,
  privacyService,
} from "../services/chapelflow";

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("ChapelFlow production workflow contracts", () => {
  it("sends member search filters without losing branch scope", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ data: [], meta: { page: 1, pageSize: 20, total: 0 } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await memberService.list({
      search: "Ada Okafor",
      branchId: "abeokuta",
      status: "active",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/members/?search=Ada+Okafor&membership_status=ACTIVE&branch=abeokuta",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("creates an attendance session with a JSON mutation payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        data: {
          id: "session-1",
          title: "Sunday Worship Service",
          status: "open",
          opensAt: "2026-08-30T08:15:00Z",
          closesAt: "2026-08-30T10:15:00Z",
          count: 0,
          lateCount: 0,
          manualCount: 0,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await attendanceService.createSession({
      title: "Sunday Worship Service",
      branchId: "abeokuta",
      date: "2026-08-30",
      opensAt: "08:15",
      closesAt: "10:15",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/attendance/sessions/",
      expect.objectContaining({
        method: "POST",
        body: expect.any(String),
      }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toMatchObject({
      branch: "abeokuta",
      label: "Sunday Worship Service",
      window_opens_at: expect.any(String),
      window_closes_at: expect.any(String),
    });
  });

  it("requires the correction reason in the attendance mutation contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        data: {
          id: "record-1",
          memberName: "Ada Okafor",
          identifier: "CU/26/101",
          time: "09:06",
          method: "manual",
          status: "present",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await attendanceService.correct("record-1", {
      status: "present",
      reason: "Verified against the signed usher register.",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/attendance/records/record-1/correct/",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toEqual({
      status: "PRESENT", reason: "Verified against the signed usher register.",
    });
  });

  it("uses scoped mutation endpoints for event registration and duty acknowledgement", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          data: { confirmationCode: "EVT-101", waitlisted: false },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await eventService.register("freshers-welcome", {
      accessibilityNeeds: "None",
    });
    await operationsService.workerAcknowledge("ushering-30-aug");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/events/freshers-welcome/register/",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/operations/workers/ushering-30-aug/acknowledge/",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("creates worker rosters separately from assignment acknowledgement", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        data: {
          id: "roster-1",
          primary: "Sunday roster",
          secondary: "30 August 2026",
          detail: "86 assignments",
          status: "draft",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await operationsService.create("workers", { title: "Sunday roster" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/operations/workers/",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("persists explicit privacy preferences through the account endpoint", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await privacyService.updatePreferences({
      email: true,
      sms: false,
      push: true,
      analytics: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/communications/preferences/me/",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          email_enabled: true,
          sms_enabled: false,
          push_enabled: true,
        }),
      }),
    );
  });
});
