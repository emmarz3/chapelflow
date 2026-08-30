import { Router } from "express";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { ApiProblem, authenticate, requirePermission } from "./http.js";

const querySchema = z.object({
  branchId: z.string().trim().max(80).optional().default("abeokuta-main"),
});

const currentBranchId = "abeokuta-main";

function weekStart(value: Date | string) {
  const date = value instanceof Date ? new Date(value) : new Date(`${value}T00:00:00Z`);
  const daysSinceMonday = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - daysSinceMonday);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

function dateKey(date: Date) {
  return date.toISOString().slice(0, 10);
}

function buildAttendanceTrend(rows: { service_date: Date | string; attendance: string }[]) {
  const totals = new Map<string, number>();
  for (const row of rows) {
    const key = dateKey(weekStart(row.service_date));
    totals.set(key, (totals.get(key) ?? 0) + Number(row.attendance));
  }

  const currentWeek = weekStart(new Date());
  return Array.from({ length: 8 }, (_, index) => {
    const start = new Date(currentWeek);
    start.setUTCDate(start.getUTCDate() - (7 - index) * 7);
    return {
      week: new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        timeZone: "UTC",
      }).format(start),
      attendance: totals.get(dateKey(start)) ?? 0,
    };
  });
}

export function dashboardRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));

  router.get("/", requirePermission("dashboard:view"), async (request, response, next) => {
    try {
      const input = querySchema.parse(request.query);
      if (input.branchId !== currentBranchId) {
        throw new ApiProblem(403, "BRANCH_ACCESS_DENIED", "You do not have access to that branch.");
      }
      const now = new Date();
      const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))
        .toISOString()
        .slice(0, 10);
      const trendStart = new Date(now);
      trendStart.setUTCDate(trendStart.getUTCDate() - 55);
      const trendStartDate = trendStart.toISOString().slice(0, 10);

      const [summary, trend] = await Promise.all([
        database.query<{
          active_members: string;
          pending_members: string;
          services_this_month: string;
          active_services: string;
          attendance_this_month: string;
        }>(`
          SELECT
            (SELECT COUNT(*) FROM users u JOIN students st ON st.user_id = u.id
              WHERE u.role = 'member' AND u.status = 'active' AND st.approval_status = 'approved')::text AS active_members,
            (SELECT COUNT(*) FROM users u JOIN students st ON st.user_id = u.id
              WHERE u.role = 'member' AND st.approval_status = 'pending')::text AS pending_members,
            (SELECT COUNT(*) FROM attendance_sessions
              WHERE service_date >= $1)::text AS services_this_month,
            (SELECT COUNT(*) FROM attendance_sessions WHERE status = 'active')::text AS active_services,
            (SELECT COUNT(*) FROM attendance_records ar
              JOIN attendance_sessions session ON session.id = ar.attendance_session_id
              WHERE session.service_date >= $1)::text AS attendance_this_month
        `, [monthStart]),
        database.query<{ service_date: Date | string; attendance: string }>(`
          SELECT session.service_date, COUNT(ar.id)::text AS attendance
            FROM attendance_sessions session
            LEFT JOIN attendance_records ar ON ar.attendance_session_id = session.id
           WHERE session.service_date >= $1
           GROUP BY session.service_date
           ORDER BY session.service_date
        `, [trendStartDate]),
      ]);
      const values = summary.rows[0];
      if (!values) throw new Error("Dashboard summary query returned no data.");

      const pending = Number(values.pending_members);
      const activeServices = Number(values.active_services);
      response.json({
        data: {
          metrics: [
            {
              label: "Active students",
              value: Number(values.active_members).toLocaleString("en-GB"),
              change: "Approved student accounts",
              trend: "neutral",
            },
            {
              label: "Pending approvals",
              value: pending.toLocaleString("en-GB"),
              change: pending ? "Awaiting chapel review" : "No registrations waiting",
              trend: pending ? "down" : "neutral",
            },
            {
              label: "Services this month",
              value: Number(values.services_this_month).toLocaleString("en-GB"),
              change: activeServices ? `${activeServices} live now` : "No service is live",
              trend: activeServices ? "up" : "neutral",
            },
            {
              label: "Attendance this month",
              value: Number(values.attendance_this_month).toLocaleString("en-GB"),
              change: "Recorded check-ins",
              trend: "neutral",
            },
          ],
          attendanceTrend: buildAttendanceTrend(trend.rows),
        },
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return next(new ApiProblem(422, "VALIDATION_ERROR", "Check the dashboard filters."));
      }
      next(error);
    }
  });

  return router;
}
