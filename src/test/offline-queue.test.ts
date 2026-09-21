import { beforeEach, describe, expect, it } from "vitest";
import {
  flushPendingAttendance,
  queueAttendanceCheckIn,
  readPendingAttendance,
  removePendingAttendance,
} from "../lib/offline-queue";

describe("offline attendance queue", () => {
  beforeEach(() => window.localStorage.clear());

  it("queues a safe check-in once and blocks local duplicates", () => {
    expect(
      queueAttendanceCheckIn({
        sessionId: "session-1",
        memberIdentifier: "CU/24/101",
        method: "manual",
      }),
    ).toBe(true);
    expect(
      queueAttendanceCheckIn({
        sessionId: "session-1",
        memberIdentifier: "CU/24/101",
        method: "manual",
      }),
    ).toBe(false);
    expect(readPendingAttendance()).toHaveLength(1);
  });

  it("removes a check-in after reconciliation", () => {
    queueAttendanceCheckIn({
      sessionId: "session-1",
      memberIdentifier: "CU/24/101",
      method: "kiosk",
    });
    const [pending] = readPendingAttendance();
    expect(pending).toBeDefined();
    removePendingAttendance(pending!.id);
    expect(readPendingAttendance()).toEqual([]);
  });

  it("removes synchronized records and retains failures for retry", async () => {
    queueAttendanceCheckIn({
      sessionId: "session-1",
      memberIdentifier: "CU/24/101",
      method: "manual",
    });
    queueAttendanceCheckIn({
      sessionId: "session-1",
      memberIdentifier: "CU/24/102",
      method: "kiosk",
    });

    const result = await flushPendingAttendance(async (item) => {
      if (item.memberIdentifier.endsWith("102"))
        throw new Error("Network error");
    });

    expect(result).toEqual({ synchronized: 1, failed: 1 });
    expect(readPendingAttendance()).toEqual([
      expect.objectContaining({
        memberIdentifier: "CU/24/102",
        method: "kiosk",
      }),
    ]);
  });
});
