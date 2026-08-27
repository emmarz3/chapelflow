export interface PendingAttendanceCheckIn {
  id: string;
  sessionId: string;
  memberIdentifier: string;
  method: "manual" | "kiosk";
  createdAt: string;
}
const STORAGE_KEY = "chapelflow-pending-attendance";
export const ATTENDANCE_QUEUE_EVENT = "chapelflow:attendance-queue-changed";

function savePendingAttendance(items: PendingAttendanceCheckIn[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  window.dispatchEvent(new Event(ATTENDANCE_QUEUE_EVENT));
}

export function readPendingAttendance(): PendingAttendanceCheckIn[] {
  try {
    return JSON.parse(
      window.localStorage.getItem(STORAGE_KEY) || "[]",
    ) as PendingAttendanceCheckIn[];
  } catch {
    return [];
  }
}

export function queueAttendanceCheckIn(
  item: Omit<PendingAttendanceCheckIn, "id" | "createdAt">,
) {
  const current = readPendingAttendance();
  if (
    current.some(
      (entry) =>
        entry.sessionId === item.sessionId &&
        entry.memberIdentifier === item.memberIdentifier,
    )
  )
    return false;
  current.push({
    ...item,
    id: crypto.randomUUID(),
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
