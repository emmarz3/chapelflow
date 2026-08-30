import { randomUUID } from "node:crypto";
import { Router } from "express";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { inTransaction } from "./db.js";
import { ApiProblem, authenticate, requirePermission } from "./http.js";

const querySchema = z.object({
  search: z.string().trim().max(160).optional().default(""),
  status: z.enum(["pending", "active", "inactive", "locked"]).optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(50),
});

export function membersRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));

  router.get("/", requirePermission("members:read"), async (request, response, next) => {
    try {
      const input = querySchema.parse(request.query);
      const values: unknown[] = [];
      const filters = ["u.role = 'member'"];
      if (input.search) {
        values.push(`%${input.search.toLowerCase()}%`);
        filters.push(`(LOWER(u.full_name) LIKE $${values.length} OR LOWER(st.matric_number) LIKE $${values.length} OR LOWER(COALESCE(st.programme, '')) LIKE $${values.length})`);
      }
      if (input.status) {
        values.push(input.status);
        filters.push(
          input.status === "pending"
            ? `st.approval_status = $${values.length}`
            : `u.status = $${values.length} AND st.approval_status = 'approved'`,
        );
      }
      const where = filters.join(" AND ");
      const total = await database.query<{ count: string }>(
        `SELECT COUNT(*)::text AS count FROM users u JOIN students st ON st.user_id = u.id WHERE ${where}`,
        values,
      );
      values.push(input.pageSize, (input.page - 1) * input.pageSize);
      const result = await database.query<{
        id: string; name: string; identifier: string; email: string;
        programme: string | null; academic_level: string | null;
        status: "pending" | "active" | "inactive" | "locked";
        approval_status: "pending" | "approved";
        last_seen: Date | null;
      }>(
        `SELECT u.id, u.full_name AS name, st.matric_number AS identifier, u.email,
                st.programme, st.academic_level, u.status, st.approval_status,
                MAX(ar.recorded_at) AS last_seen
           FROM users u JOIN students st ON st.user_id = u.id
           LEFT JOIN attendance_records ar ON ar.student_id = st.id
          WHERE ${where}
          GROUP BY u.id, st.matric_number, st.programme, st.academic_level, st.approval_status
          ORDER BY CASE WHEN st.approval_status = 'pending' THEN 0 ELSE 1 END, u.full_name
          LIMIT $${values.length - 1} OFFSET $${values.length}`,
        values,
      );
      response.json({
        data: result.rows.map((row) => ({
          id: row.id,
          name: row.name,
          identifier: row.identifier,
          email: row.email,
          programme: row.programme ?? "",
          level: row.academic_level ?? "",
          department: "",
          status:
            row.approval_status === "pending"
              ? "pending"
              : row.status === "locked"
                ? "inactive"
                : row.status,
          attendanceRate: 0,
          lastSeen: row.last_seen?.toISOString() ?? "",
        })),
        page: input.page,
        pageSize: input.pageSize,
        total: Number(total.rows[0]?.count ?? 0),
      });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(422, "VALIDATION_ERROR", "Check the member filters."));
      next(error);
    }
  });

  router.post("/:id/approve", requirePermission("members:write"), async (request, response, next) => {
    try {
      const id = z.string().uuid().parse(request.params.id);
      await inTransaction(database, async (client) => {
        const current = await client.query<{
          status: string;
          role: string;
          approval_status: string;
        }>(
          `SELECT u.status, u.role, st.approval_status
             FROM users u JOIN students st ON st.user_id = u.id
            WHERE u.id = $1 FOR UPDATE`,
          [id],
        );
        if (!current.rows[0] || current.rows[0].role !== "member") {
          throw new ApiProblem(404, "MEMBER_NOT_FOUND", "Student registration not found.");
        }
        if (current.rows[0].approval_status !== "pending") {
          throw new ApiProblem(409, "MEMBER_NOT_PENDING", "Only a pending student registration can be approved.");
        }
        await client.query("UPDATE users SET status = 'active', updated_at = NOW() WHERE id = $1", [id]);
        await client.query(
          "UPDATE students SET approval_status = 'approved', updated_at = NOW() WHERE user_id = $1",
          [id],
        );
        await client.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'student.approved', 'user', $3)`,
          [randomUUID(), request.authUser!.id, id],
        );
      });
      response.json({ data: { id, status: "active" } });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(404, "MEMBER_NOT_FOUND", "Student registration not found."));
      next(error);
    }
  });

  return router;
}
