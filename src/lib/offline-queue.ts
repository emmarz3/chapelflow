interface PendingAttendanceBase {
  id: string;
  sessionId: string;
  createdAt: string;
}
export type PendingAttendanceCheckIn =
  | (PendingAttendanceBase & { kind: "student-code"; code: string })
  | (PendingAttendanceBase & {
      kind?: "staff";
      branchId?: string;
      memberIdentifier: string;
      method: "manual" | "kiosk";
    });
const STORAGE_KEY = "chapelflow-pending-attendance";
export const ATTENDANCE_QUEUE_EVENT = "chapelflow:attendance-queue-changed";

function savePendingAttendance(items: PendingAttendanceCheckIn[]) {
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  window.dispatchEvent(new Event(ATTENDANCE_QUEUE_EVENT));
}

export function readPendingAttendance(): PendingAttendanceCheckIn[] {
  try {
    // Migrate any previous localStorage queue, then remove its persistent PII copy.
    const legacyQueue = window.localStorage.getItem(STORAGE_KEY);
    if (legacyQueue) {
      if (!window.sessionStorage.getItem(STORAGE_KEY)) {
        window.sessionStorage.setItem(STORAGE_KEY, legacyQueue);
      }
      window.localStorage.removeItem(STORAGE_KEY);
    }
    return JSON.parse(
      window.sessionStorage.getItem(STORAGE_KEY) || "[]",
    ) as PendingAttendanceCheckIn[];
  } catch {
    return [];
  }
}

export function queueAttendanceCheckIn(
  item: {
    sessionId: string;
    memberIdentifier: string;
    method: "manual" | "kiosk";
    branchId: string;
  },
) {
  const current = readPendingAttendance();
  if (
    current.some(
      (entry) =>
        entry.sessionId === item.sessionId &&
        entry.kind !== "student-code" &&
        entry.memberIdentifier === item.memberIdentifier,
    )
  )
    return false;
  current.push({
    ...item,
    kind: "staff",
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  });
  savePendingAttendance(current);
  return true;
}

export function queueStudentAttendanceCode(sessionId: string, code: string) {
  const current = readPendingAttendance();
  if (current.some((entry) => entry.kind === "student-code" && entry.sessionId === sessionId)) return false;
  current.push({
    id: crypto.randomUUID(),
    sessionId,
    kind: "student-code",
    code,
    createdAt: new Date().toISOString(),
  });
  savePendingAttendance(current);
  return true;
}

export function removePendingAttendance(id: string) {
  savePendingAttendance(
    readPendingAttendance().filter((item) => item.id !== id),
  );
}

export interface AttendanceSyncResult {
  synchronized: number;
  failed: number;
}

let activeFlush: Promise<AttendanceSyncResult> | null = null;

export function flushPendingAttendance(
  synchronize: (item: PendingAttendanceCheckIn) => Promise<unknown>,
) {
  if (activeFlush) return activeFlush;
  activeFlush = (async () => {
    let synchronized = 0;
    let failed = 0;
    for (const item of readPendingAttendance()) {
      try {
        await synchronize(item);
        removePendingAttendance(item.id);
        synchronized += 1;
      } catch {
        failed += 1;
      }
    }
    return { synchronized, failed };
  })().finally(() => {
    activeFlush = null;
  });
  return activeFlush;
}
