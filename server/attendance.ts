import { randomUUID } from "node:crypto";
import { Router } from "express";
import QRCode from "qrcode";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { inTransaction } from "./db.js";
import { ApiProblem, authenticate, requirePermission } from "./http.js";
import { signQrToken, verifyQrToken } from "./security.js";

const uuid = z.string().uuid();
const sessionSchema = z.object({
  title: z.string().trim().min(3).max(180),
  date: z.iso.date(),
  opensAt: z.string().regex(/^\d{2}:\d{2}$/),
  closesAt: z.string().regex(/^\d{2}:\d{2}$/),
  serviceType: z.string().trim().min(2).max(80).optional().default("chapel_service"),
});
const scanSchema = z.object({ token: z.string().min(20).max(2_048), sessionId: uuid, idempotencyKey: uuid });
const manualSchema = z.object({
  identifier: z.string().trim().min(3).max(80),
  sessionId: uuid,
  reason: z.string().trim().min(3).max(500),
  idempotencyKey: uuid,
});

interface ActiveSessionRow {
  id: string;
  title: string;
  service_type: string;
  service_date: string;
  starts_at: Date;
  ends_at: Date;
  status: "active";
  opened_at: Date;
}

interface StudentRow {
  id: string;
  user_id: string;
  full_name: string;
  matric_number: string;
  programme: string | null;
  academic_level: string | null;
  photo_url: string | null;
  pass_status: "active" | "revoked";
  account_status: "active" | "inactive" | "locked";
}

async function activeSession(database: Pick<Database, "query">) {
  const result = await database.query<ActiveSessionRow>(
    "SELECT * FROM attendance_sessions WHERE status = 'active' ORDER BY opened_at DESC LIMIT 1",
  );
  return result.rows[0] ?? null;
}

function sessionResponse(session: ActiveSessionRow, count = 0) {
  return {
    id: session.id,
    title: session.title,
    serviceType: session.service_type,
    date: session.service_date,
    status: session.status,
    opensAt: session.starts_at.toISOString(),
    closesAt: session.ends_at.toISOString(),
    openedAt: session.opened_at.toISOString(),
    count,
  };
}

async function recentRecords(database: Pick<Database, "query">, sessionId: string, usherId?: string) {
  const values: unknown[] = [sessionId];
  const usherFilter = usherId ? "AND ar.recorded_by_usher_id = $2" : "";
  if (usherId) values.push(usherId);
  const result = await database.query<{
    id: string; full_name: string; matric_number: string; programme: string | null;
    academic_level: string | null; recorded_at: Date; method: "qr_scan" | "manual";
    status: "present" | "late" | "excused";
  }>(
    `SELECT ar.id, u.full_name, st.matric_number, st.programme, st.academic_level,
            ar.recorded_at, ar.method, ar.status
       FROM attendance_records ar
       JOIN students st ON st.id = ar.student_id
       JOIN users u ON u.id = st.user_id
      WHERE ar.attendance_session_id = $1 ${usherFilter}
      ORDER BY ar.recorded_at DESC LIMIT 20`,
    values,
  );
  return result.rows.map((row) => ({
    id: row.id,
    memberName: row.full_name,
    identifier: row.matric_number,
    programme: row.programme,
    level: row.academic_level,
    recordedAt: row.recorded_at.toISOString(),
    time: row.recorded_at.toISOString(),
    method: row.method === "qr_scan" ? "qr" : "manual",
    status: row.status,
  }));
}

async function createAttendance(
  database: Database,
  input: {
    sessionId: string;
    student: StudentRow;
    actorId: string;
    method: "qr_scan" | "manual";
    reason?: string;
    idempotencyKey: string;
    scannerMetadata: Record<string, string | undefined>;
  },
) {
  return inTransaction(database, async (client) => {
    const session = await activeSession(client as unknown as Database);
    if (!session || session.id !== input.sessionId) {
      throw new ApiProblem(409, "NO_ACTIVE_SESSION", "No active attendance session is accepting scans.");
    }
    if (input.student.account_status !== "active" || input.student.pass_status !== "active") {
      throw new ApiProblem(403, "STUDENT_INACTIVE", "This student account is currently inactive. Contact an administrator.");
    }
    const duplicate = await client.query<{ id: string; recorded_at: Date }>(
      `SELECT id, recorded_at FROM attendance_records
        WHERE attendance_session_id = $1 AND student_id = $2`,
      [session.id, input.student.id],
    );
    if (duplicate.rows[0]) {
      return { result: "duplicate" as const, record: duplicate.rows[0] };
    }
    const id = randomUUID();
    const inserted = await client.query<{ id: string; recorded_at: Date }>(
      `INSERT INTO attendance_records
        (id, attendance_session_id, student_id, recorded_by_usher_id, method, scanner_metadata, exception_reason, idempotency_key)
       VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
       ON CONFLICT (attendance_session_id, student_id) DO NOTHING
       RETURNING id, recorded_at`,
      [id, session.id, input.student.id, input.actorId, input.method, JSON.stringify(input.scannerMetadata), input.reason ?? null, input.idempotencyKey],
    );
    if (!inserted.rows.length) {
      const existing = await client.query<{ id: string; recorded_at: Date }>(
        `SELECT id, recorded_at FROM attendance_records
          WHERE attendance_session_id = $1 AND student_id = $2`,
        [session.id, input.student.id],
      );
      return { result: "duplicate" as const, record: existing.rows[0]! };
    }
    await client.query(
      `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id, metadata)
       VALUES ($1, $2, $3, 'attendance_record', $4, $5::jsonb)`,
      [randomUUID(), input.actorId, input.method === "qr_scan" ? "attendance.scanned" : "attendance.manual_recorded", id, JSON.stringify({ sessionId: session.id, method: input.method })],
    );
    return { result: "recorded" as const, record: inserted.rows[0]! };
  });
}

function scanResult(result: Awaited<ReturnType<typeof createAttendance>>, student: StudentRow, session: ActiveSessionRow) {
  return {
    result: result.result,
    record: {
      id: result.record.id,
      recordedAt: result.record.recorded_at.toISOString(),
      student: {
        name: student.full_name,
        identifier: student.matric_number,
        programme: student.programme,
        level: student.academic_level,
      },
      session: { id: session.id, title: session.title },
    },
  };
}

export function attendanceRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));

  router.get("/pass", requirePermission("attendance:read"), async (request, response, next) => {
    try {
      if (request.authUser!.role !== "member") throw new ApiProblem(403, "STUDENT_ONLY", "Only student accounts have a chapel pass.");
      const students = await database.query<StudentRow & { qr_pass_id: string }>(
        `SELECT st.*, u.full_name, u.status AS account_status
           FROM students st JOIN users u ON u.id = st.user_id WHERE st.user_id = $1`,
        [request.authUser!.id],
      );
      const student = students.rows[0];
      if (!student) throw new ApiProblem(404, "STUDENT_NOT_FOUND", "No student profile is linked to this account.");
      const session = await activeSession(database);
      const token = session && student.pass_status === "active" && student.account_status === "active"
        ? signQrToken({ passId: student.qr_pass_id, sessionId: session.id }, config.CHAPELFLOW_QR_SIGNING_SECRET)
        : null;
      response.set("Cache-Control", "no-store");
      response.json({ data: {
        student: {
          name: student.full_name,
          identifier: student.matric_number,
          programme: student.programme,
          level: student.academic_level,
          photoUrl: student.photo_url,
        },
        passStatus: student.account_status === "active" ? student.pass_status : "inactive",
        session: session ? { id: session.id, title: session.title } : null,
        token,
        imageDataUrl: token ? await QRCode.toDataURL(token, { errorCorrectionLevel: "M", margin: 2, width: 640 }) : null,
        expiresAt: token ? new Date(Date.now() + 120_000).toISOString() : null,
      } });
    } catch (error) { next(error); }
  });

  router.get("/history/me", requirePermission("attendance:read"), async (request, response, next) => {
    try {
      const result = await database.query(
        `SELECT ats.title, ats.service_date AS date, ar.recorded_at, ar.status
           FROM attendance_records ar JOIN attendance_sessions ats ON ats.id = ar.attendance_session_id
           JOIN students st ON st.id = ar.student_id
          WHERE st.user_id = $1 ORDER BY ar.recorded_at DESC LIMIT 100`,
        [request.authUser!.id],
      );
      response.json({ data: result.rows });
    } catch (error) { next(error); }
  });

  router.get("/sessions/active", requirePermission("attendance:scan"), async (request, response, next) => {
    try {
      const session = await activeSession(database);
      if (!session) return response.json({ data: null });
      const countResult = await database.query<{ count: string }>(
        "SELECT COUNT(*)::text AS count FROM attendance_records WHERE attendance_session_id = $1",
        [session.id],
      );
      response.json({ data: {
        session: sessionResponse(session, Number(countResult.rows[0]?.count ?? 0)),
        recent: await recentRecords(database, session.id, request.authUser!.id),
      } });
    } catch (error) { next(error); }
  });

  router.get("/sessions/current", requirePermission("attendance:write"), async (_request, response, next) => {
    try {
      const session = await activeSession(database);
      if (!session) throw new ApiProblem(404, "NO_ACTIVE_SESSION", "There is no active attendance session.");
      const records = await recentRecords(database, session.id);
      const totals = await database.query<{
        count: string;
        late_count: string;
        manual_count: string;
      }>(
        `SELECT COUNT(*)::text AS count,
                COUNT(*) FILTER (WHERE status = 'late')::text AS late_count,
                COUNT(*) FILTER (WHERE method = 'manual')::text AS manual_count
           FROM attendance_records WHERE attendance_session_id = $1`,
        [session.id],
      );
      response.json({ data: {
        session: {
          ...sessionResponse(session, Number(totals.rows[0]?.count ?? 0)),
          lateCount: Number(totals.rows[0]?.late_count ?? 0),
          manualCount: Number(totals.rows[0]?.manual_count ?? 0),
        },
        records,
      } });
    } catch (error) { next(error); }
  });

  router.get("/sessions", requirePermission("attendance:write"), async (request, response, next) => {
    try {
      const status = z
        .enum(["scheduled", "active", "closed"])
        .optional()
        .parse(request.query.status);
      const result = await database.query<{
        id: string;
        title: string;
        service_type: string;
        service_date: string;
        starts_at: Date;
        ends_at: Date;
        status: "scheduled" | "active" | "closed";
        created_at: Date;
      }>(
        `SELECT ats.id, ats.title, ats.service_type, ats.service_date,
                ats.starts_at, ats.ends_at, ats.status, ats.created_at
           FROM attendance_sessions ats
          ORDER BY ats.service_date DESC, ats.starts_at DESC LIMIT 100`,
      );
      response.json({
        data: result.rows
          .filter((row) => !status || row.status === status)
          .map((row) => ({
            id: row.id,
            title: row.title,
            serviceType: row.service_type,
            date: row.service_date,
            startsAt: row.starts_at.toISOString(),
            endsAt: row.ends_at.toISOString(),
            status: row.status,
            createdAt: row.created_at.toISOString(),
          })),
      });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(422, "VALIDATION_ERROR", "The session status filter is invalid."));
      next(error);
    }
  });

  router.post("/scan", requirePermission("attendance:scan"), async (request, response, next) => {
    try {
      const input = scanSchema.parse(request.body);
      const claims = verifyQrToken(input.token, config.CHAPELFLOW_QR_SIGNING_SECRET);
      if (!claims || claims.sessionId !== input.sessionId) throw new ApiProblem(422, "INVALID_PASS", "This QR code could not be verified.");
      const students = await database.query<StudentRow>(
        `SELECT st.id, st.user_id, st.matric_number, st.programme, st.academic_level, st.photo_url,
                st.pass_status, u.full_name, u.status AS account_status
           FROM students st JOIN users u ON u.id = st.user_id WHERE st.qr_pass_id = $1`,
        [claims.passId],
      );
      const student = students.rows[0];
      if (!student) throw new ApiProblem(422, "INVALID_PASS", "This QR code could not be verified.");
      const session = await activeSession(database);
      if (!session || session.id !== input.sessionId) throw new ApiProblem(409, "NO_ACTIVE_SESSION", "No active attendance session is accepting scans.");
      const result = await createAttendance(database, {
        sessionId: input.sessionId,
        student,
        actorId: request.authUser!.id,
        method: "qr_scan",
        idempotencyKey: input.idempotencyKey,
        scannerMetadata: { userAgent: request.get("user-agent"), ip: request.ip },
      });
      response.status(result.result === "recorded" ? 201 : 200).json({ data: scanResult(result, student, session) });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(422, "INVALID_PASS", "This QR code could not be verified."));
      next(error);
    }
  });

  router.post("/manual", requirePermission("attendance:manual"), async (request, response, next) => {
    try {
      const input = manualSchema.parse(request.body);
      const students = await database.query<StudentRow>(
        `SELECT st.id, st.user_id, st.matric_number, st.programme, st.academic_level, st.photo_url,
                st.pass_status, u.full_name, u.status AS account_status
           FROM students st JOIN users u ON u.id = st.user_id WHERE LOWER(st.matric_number) = $1 LIMIT 1`,
        [input.identifier.toLowerCase()],
      );
      const student = students.rows[0];
      if (!student) throw new ApiProblem(404, "STUDENT_NOT_FOUND", "No eligible student matches that identifier.");
      const session = await activeSession(database);
      if (!session || session.id !== input.sessionId) throw new ApiProblem(409, "NO_ACTIVE_SESSION", "No active attendance session is accepting scans.");
      const result = await createAttendance(database, {
        sessionId: input.sessionId, student, actorId: request.authUser!.id,
        method: "manual", reason: input.reason, idempotencyKey: input.idempotencyKey,
        scannerMetadata: { userAgent: request.get("user-agent"), ip: request.ip },
      });
      response.status(result.result === "recorded" ? 201 : 200).json({ data: scanResult(result, student, session) });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(422, "VALIDATION_ERROR", "Enter a valid identifier and reason."));
      next(error);
    }
  });

  router.post("/sessions", requirePermission("attendance:write"), async (request, response, next) => {
    try {
      const input = sessionSchema.parse(request.body);
      const startsAt = new Date(`${input.date}T${input.opensAt}:00+01:00`);
      const endsAt = new Date(`${input.date}T${input.closesAt}:00+01:00`);
      if (endsAt <= startsAt) throw new ApiProblem(422, "VALIDATION_ERROR", "Closing time must be after opening time.");
      const id = randomUUID();
      await database.query(
        `INSERT INTO attendance_sessions
          (id, title, service_type, service_date, starts_at, ends_at, created_by, status)
         VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled')`,
        [id, input.title, input.serviceType, input.date, startsAt, endsAt, request.authUser!.id],
      );
      await database.query(
        `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
         VALUES ($1, $2, 'attendance_session.created', 'attendance_session', $3)`,
        [randomUUID(), request.authUser!.id, id],
      );
      response.status(201).json({ data: { id, title: input.title, status: "scheduled" } });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(422, "VALIDATION_ERROR", "Check the attendance session details."));
      next(error);
    }
  });

  router.patch("/sessions/:id/activate", requirePermission("attendance:write"), async (request, response, next) => {
    try {
      const id = uuid.parse(request.params.id);
      await inTransaction(database, async (client) => {
        const current = await client.query<{ status: string }>(
          "SELECT status FROM attendance_sessions WHERE id = $1 FOR UPDATE",
          [id],
        );
        if (current.rows[0]?.status !== "scheduled") {
          throw new ApiProblem(409, "SESSION_NOT_SCHEDULED", "Only a scheduled session can be activated.");
        }
        await client.query(
          `UPDATE attendance_sessions SET status = 'active', opened_at = NOW(), updated_at = NOW()
            WHERE id = $1`, [id],
        );
        await client.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'attendance_session.activated', 'attendance_session', $3)`,
          [randomUUID(), request.authUser!.id, id],
        );
      });
      response.json({ data: { id, status: "active" } });
    } catch (error) {
      if (typeof error === "object" && error && "code" in error && error.code === "23505") return next(new ApiProblem(409, "ACTIVE_SESSION_EXISTS", "Close the current active session first."));
      if (error instanceof z.ZodError) return next(new ApiProblem(404, "SESSION_NOT_FOUND", "Attendance session not found."));
      next(error);
    }
  });

  router.patch("/sessions/:id/close", requirePermission("attendance:write"), async (request, response, next) => {
    try {
      const id = uuid.parse(request.params.id);
      await inTransaction(database, async (client) => {
        const current = await client.query<{ status: string }>(
          "SELECT status FROM attendance_sessions WHERE id = $1 FOR UPDATE",
          [id],
        );
        if (current.rows[0]?.status !== "active") {
          throw new ApiProblem(409, "SESSION_NOT_ACTIVE", "Only an active session can be closed.");
        }
        await client.query(
          `UPDATE attendance_sessions SET status = 'closed', closed_at = NOW(), updated_at = NOW()
            WHERE id = $1`, [id],
        );
        await client.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'attendance_session.closed', 'attendance_session', $3)`,
          [randomUUID(), request.authUser!.id, id],
        );
      });
      response.json({ data: { id, status: "closed" } });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(404, "SESSION_NOT_FOUND", "Attendance session not found."));
      next(error);
    }
  });

  router.patch("/records/:id", requirePermission("attendance:write"), async (request, response, next) => {
    try {
      const id = uuid.parse(request.params.id);
      const input = z.object({ status: z.enum(["present", "late", "excused"]), reason: z.string().trim().min(3).max(500) }).parse(request.body);
      const result = await database.query(
        `UPDATE attendance_records SET status = $2, exception_reason = $3, updated_at = NOW()
          WHERE id = $1 RETURNING id`, [id, input.status, input.reason],
      );
      if (!result.rows.length) throw new ApiProblem(404, "RECORD_NOT_FOUND", "Attendance record not found.");
      await database.query(
        `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id, metadata)
         VALUES ($1, $2, 'attendance.corrected', 'attendance_record', $3, $4::jsonb)`,
        [randomUUID(), request.authUser!.id, id, JSON.stringify({ status: input.status, reason: input.reason })],
      );
      response.json({ data: { id, status: input.status } });
    } catch (error) {
      if (error instanceof z.ZodError) return next(new ApiProblem(422, "VALIDATION_ERROR", "Enter a valid status and reason."));
      next(error);
    }
  });

  router.get("/sessions/:id/qr", requirePermission("attendance:write"), async (request, response, next) => {
    try {
      const id = uuid.parse(request.params.id);
      const imageDataUrl = await QRCode.toDataURL(`${config.APP_ORIGIN}/app/chapel-pass`, { width: 560, margin: 2 });
      response.json({ data: { imageDataUrl, reference: `SESSION-${id.slice(0, 8).toUpperCase()}`, expiresAt: new Date(Date.now() + 60_000).toISOString() } });
    } catch (error) { next(error); }
  });

  return router;
}
