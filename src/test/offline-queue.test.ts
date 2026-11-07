import { beforeEach, describe, expect, it } from "vitest";
import {
  flushPendingAttendance,
  queueAttendanceCheckIn,
  readPendingAttendance,
  removePendingAttendance,
} from "../lib/offline-queue";

describe("offline attendance queue", () => {
<<<<<<< HEAD
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
=======
  beforeEach(() => window.localStorage.clear());
>>>>>>> origin/main

  it("queues a safe check-in once and blocks local duplicates", () => {
    expect(
      queueAttendanceCheckIn({
        sessionId: "session-1",
        branchId: "branch-1",
        memberIdentifier: "CU/24/101",
        method: "manual",
      }),
    ).toBe(true);
    expect(
      queueAttendanceCheckIn({
        sessionId: "session-1",
        branchId: "branch-1",
        memberIdentifier: "CU/24/101",
        method: "manual",
      }),
    ).toBe(false);
    expect(readPendingAttendance()).toHaveLength(1);
<<<<<<< HEAD
    expect(window.localStorage.getItem("chapelflow-pending-attendance")).toBeNull();
    expect(window.sessionStorage.getItem("chapelflow-pending-attendance")).not.toBeNull();
=======
>>>>>>> origin/main
  });

  it("removes a check-in after reconciliation", () => {
    queueAttendanceCheckIn({
      sessionId: "session-1",
      branchId: "branch-1",
      memberIdentifier: "CU/24/101",
      method: "kiosk",
    });
    const [pending] = readPendingAttendance();
    expect(pending).toBeDefined();
    removePendingAttendance(pending!.id);
    expect(readPendingAttendance()).toEqual([]);
  });

<<<<<<< HEAD
  it("migrates an old persistent queue into session storage and clears its old copy", () => {
    window.localStorage.setItem("chapelflow-pending-attendance", JSON.stringify([{
      id: "legacy-1",
      sessionId: "session-1",
      branchId: "branch-1",
      memberIdentifier: "CU/24/101",
      method: "manual",
      createdAt: new Date().toISOString(),
    }]));

    expect(readPendingAttendance()).toHaveLength(1);
    expect(window.localStorage.getItem("chapelflow-pending-attendance")).toBeNull();
    expect(window.sessionStorage.getItem("chapelflow-pending-attendance")).not.toBeNull();
  });

=======
>>>>>>> origin/main
  it("removes synchronized records and retains failures for retry", async () => {
    queueAttendanceCheckIn({
      sessionId: "session-1",
      branchId: "branch-1",
      memberIdentifier: "CU/24/101",
      method: "manual",
    });
    queueAttendanceCheckIn({
      sessionId: "session-1",
      branchId: "branch-1",
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
