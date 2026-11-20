import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "./ui";
import { flushPendingAttendance } from "../lib/offline-queue";
import { attendanceService } from "../services/chapelflow";
import { useAuth } from "../features/auth-context";

export function OfflineAttendanceSync() {
  const { user } = useAuth();
  const client = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    if (!user) return;
    let active = true;
    const synchronize = async () => {
      if (!navigator.onLine) return;
      const result = await flushPendingAttendance(async (item) => {
        if (item.memberIdentifier && item.method) {
          await attendanceService.syncOffline({
            id: item.id,
            sessionId: item.sessionId,
            memberIdentifier: item.memberIdentifier,
            method: item.method,
            createdAt: item.createdAt,
          }, item.branchId || user.branchId);
        } else {
          throw new Error("Queued attendance data is incomplete.");
        }
      });
      if (!active || (!result.synchronized && !result.failed)) return;
      if (result.synchronized) {
        toast(
          `${result.synchronized} offline check-in${result.synchronized === 1 ? "" : "s"} synchronized.`,
        );
        void client.invalidateQueries({ queryKey: ["attendance"] });
        void client.invalidateQueries({ queryKey: ["attendance-records"] });
        void client.invalidateQueries({ queryKey: ["attendance-history", "me"] });
        void client.invalidateQueries({ queryKey: ["attendance-pass"] });
      }
      if (result.failed) {
        toast(
          `${result.failed} offline check-in${result.failed === 1 ? " remains" : "s remain"} queued for retry.`,
          "error",
        );
      }
    };
    void synchronize();
    window.addEventListener("online", synchronize);
    return () => {
      active = false;
      window.removeEventListener("online", synchronize);
    };
  }, [client, toast, user]);

  return null;
}
