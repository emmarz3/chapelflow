// @vitest-environment node
import { randomUUID } from "node:crypto";
import { newDb } from "pg-mem";
import request from "supertest";
import { beforeEach, describe, expect, it } from "vitest";
import { createApp } from "./app.js";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { runMigrations } from "./migrations.js";
import { hashPassword, signQrToken } from "./security.js";
import { seedAdministrator, seedUshers } from "./seed.js";
import { seedOrganization } from "./organization-seed.js";

const config: AppConfig = {
  NODE_ENV: "test",
  PORT: 8000,
  DATABASE_URL: "postgresql://test",
  APP_ORIGIN: "http://localhost:5173",
  CHAPELFLOW_SESSION_SECRET: "test-session-secret-that-is-long-enough",
  CHAPELFLOW_QR_SIGNING_SECRET: "test-qr-signing-secret-that-is-long-enough",
};

let database: Database;
let app: ReturnType<typeof createApp>;
let registrationUnitId: string;
let registrationFellowshipId: string;

async function addUser(input: {
  username: string;
  role: string;
  status?: string;
  student?: { matric: string; passStatus?: string };
}) {
  const userId = randomUUID();
  await database.query(
    `INSERT INTO users (id, username, email, password_hash, full_name, role, status)
     VALUES ($1, $2, $3, $4, $5, $6, $7)`,
    [
      userId,
      input.username,
      `${input.username}@example.edu.ng`,
      await hashPassword("secure-password-1"),
      input.username,
      input.role,
      input.status ?? "active",
    ],
  );
  if (input.student) {
    await database.query(
      `INSERT INTO students
        (id, user_id, matric_number, programme, academic_level, qr_pass_id, pass_status, approval_status)
       VALUES ($1, $2, $3, 'Computer Science', '300', $4, $5, 'approved')`,
      [
        randomUUID(),
        userId,
        input.student.matric,
        randomUUID(),
        input.student.passStatus ?? "active",
      ],
    );
  }
  return userId;
}

async function login(identifier: string) {
  const response = await request(app)
    .post("/api/auth/login")
    .send({ identifier, password: "secure-password-1" });
  expect(response.status).toBe(200);
  return response.headers["set-cookie"] as unknown as string[];
}

beforeEach(async () => {
  const memory = newDb({
    autoCreateForeignKeyIndices: true,
    noAstCoverageCheck: true,
  });
  const adapter = memory.adapters.createPg();
  database = new adapter.Pool() as unknown as Database;
  await runMigrations(database);
  await seedOrganization(database);
  const registrationCommunities = await database.query<{
    id: string;
    slug: string;
  }>(
    "SELECT id, slug FROM communities WHERE slug IN ('music', 'love-campus-fellowship')",
  );
  registrationUnitId = registrationCommunities.rows.find(
    (row) => row.slug === "music",
  )!.id;
  registrationFellowshipId = registrationCommunities.rows.find(
    (row) => row.slug === "love-campus-fellowship",
  )!.id;
  app = createApp(database, config);
});

describe("secure chapel attendance flow", () => {
  it("enforces roles, signed passes, duplicate protection, manual audit, and closure", async () => {
    await addUser({ username: "admin", role: "chapel_admin" });
    await addUser({ username: "usher", role: "attendance_usher" });
    await addUser({
      username: "student",
      role: "member",
      student: { matric: "CU/26/101" },
    });
    const adminCookie = await login("admin");
    const usherCookie = await login("usher");
    const studentCookie = await login("student");

    const registration = await request(app).post("/api/auth/register").send({
      email: "pending.student@example.edu.ng",
      password: "secure-password-2",
      firstName: "Pending",
      lastName: "Student",
      identifier: "CU/26/150",
      programme: "Computer Science",
      level: "200",
      unitCommunityId: registrationUnitId,
      fellowshipCommunityId: registrationFellowshipId,
      acceptedPolicies: true,
    });
    expect(registration.status).toBe(201);
    expect(registration.body.data.approvalRequired).toBe(true);
    expect(
      (
        await request(app).post("/api/auth/login").send({
          identifier: "CU/26/150",
          password: "secure-password-2",
        })
      ).status,
    ).toBe(401);
    const pending = await request(app)
      .get("/api/members?status=pending")
      .set("Cookie", adminCookie);
    expect(pending.body.data).toHaveLength(1);
    expect(
      (
        await request(app)
          .post(`/api/members/${pending.body.data[0].id}/approve`)
          .set("Cookie", usherCookie)
      ).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .post(`/api/members/${pending.body.data[0].id}/approve`)
          .set("Cookie", adminCookie)
      ).status,
    ).toBe(200);
    expect(
      (
        await request(app).post("/api/auth/login").send({
          identifier: "CU/26/150",
          password: "secure-password-2",
        })
      ).status,
    ).toBe(200);

    const created = await request(app)
      .post("/api/attendance/sessions")
      .set("Cookie", adminCookie)
      .send({
        title: "Sunday Chapel Service",
        date: "2026-08-30",
        opensAt: "08:00",
        closesAt: "10:30",
      });
    expect(created.status).toBe(201);
    const sessionId = created.body.data.id as string;
    const scheduled = await request(app)
      .get("/api/attendance/sessions?status=scheduled")
      .set("Cookie", adminCookie);
    expect(scheduled.status).toBe(200);
    expect(scheduled.body.data).toMatchObject([
      { id: sessionId, title: "Sunday Chapel Service", status: "scheduled" },
    ]);

    expect(
      (
        await request(app)
          .patch(`/api/attendance/sessions/${sessionId}/activate`)
          .set("Cookie", usherCookie)
      ).status,
    ).toBe(403);
    const activated = await request(app)
      .patch(`/api/attendance/sessions/${sessionId}/activate`)
      .set("Cookie", adminCookie);
    expect(activated.status).toBe(200);

    const pass = await request(app)
      .get("/api/attendance/pass")
      .set("Cookie", studentCookie);
    expect(pass.status).toBe(200);
    expect(pass.body.data.token).toMatch(/^cf1\./);
    expect(pass.body.data.token).not.toContain("CU/26/101");
    expect(
      (
        await request(app)
          .get("/api/attendance/sessions/current")
          .set("Cookie", studentCookie)
      ).status,
    ).toBe(403);

    const payload = {
      token: pass.body.data.token,
      sessionId,
      idempotencyKey: randomUUID(),
    };
    expect(
      (
        await request(app)
          .post("/api/attendance/scan")
          .set("Cookie", studentCookie)
          .send(payload)
      ).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .post("/api/attendance/scan")
          .set("Cookie", usherCookie)
          .send({ ...payload, token: `${payload.token}x` })
      ).body.code,
    ).toBe("INVALID_PASS");
    const unknownToken = signQrToken(
      { passId: randomUUID(), sessionId },
      config.CHAPELFLOW_QR_SIGNING_SECRET,
    );
    expect(
      (
        await request(app)
          .post("/api/attendance/scan")
          .set("Cookie", usherCookie)
          .send({ ...payload, token: unknownToken })
      ).body.code,
    ).toBe("INVALID_PASS");

    await addUser({
      username: "inactive-student",
      role: "member",
      status: "inactive",
      student: { matric: "CU/26/199" },
    });
    const inactivePass = await database.query<{ qr_pass_id: string }>(
      "SELECT qr_pass_id FROM students WHERE matric_number = 'CU/26/199'",
    );
    const inactiveToken = signQrToken(
      { passId: inactivePass.rows[0]!.qr_pass_id, sessionId },
      config.CHAPELFLOW_QR_SIGNING_SECRET,
    );
    const inactiveScan = await request(app)
      .post("/api/attendance/scan")
      .set("Cookie", usherCookie)
      .send({ ...payload, token: inactiveToken, idempotencyKey: randomUUID() });
    expect(inactiveScan.body.code).toBe("STUDENT_INACTIVE");

    const first = await request(app)
      .post("/api/attendance/scan")
      .set("Cookie", usherCookie)
      .send(payload);
    const second = await request(app)
      .post("/api/attendance/scan")
      .set("Cookie", usherCookie)
      .send({ ...payload, idempotencyKey: randomUUID() });
    expect(first.body.data.result).toBe("recorded");
    expect(second.body.data.result).toBe("duplicate");
    const count = await database.query<{ count: string }>(
      "SELECT COUNT(*)::text AS count FROM attendance_records",
    );
    expect(Number(count.rows[0]?.count)).toBe(1);

    await addUser({
      username: "student2",
      role: "member",
      student: { matric: "CU/26/102" },
    });
    const manual = await request(app)
      .post("/api/attendance/manual")
      .set("Cookie", usherCookie)
      .send({
        identifier: "CU/26/102",
        sessionId,
        reason: "Student phone screen is damaged",
        idempotencyKey: randomUUID(),
      });
    expect(manual.status).toBe(201);
    expect(manual.body.data.result).toBe("recorded");

    expect(
      (
        await request(app)
          .patch(`/api/attendance/sessions/${sessionId}/close`)
          .set("Cookie", adminCookie)
      ).status,
    ).toBe(200);
    const afterClose = await request(app)
      .post("/api/attendance/scan")
      .set("Cookie", usherCookie)
      .send({ ...payload, idempotencyKey: randomUUID() });
    expect(afterClose.body.code).toBe("NO_ACTIVE_SESSION");

    const audit = await database.query<{ action: string }>(
      "SELECT action FROM audit_events ORDER BY created_at",
    );
    expect(audit.rows.map((row) => row.action)).toEqual(
      expect.arrayContaining([
        "attendance_session.created",
        "attendance_session.activated",
        "attendance.scanned",
        "attendance.manual_recorded",
        "attendance_session.closed",
      ]),
    );
  }, 15_000);

  it("seeds exactly two restricted usher accounts idempotently without exposing passwords", async () => {
    const environment = {
      CHAPELFLOW_USHER_01_USERNAME: "usher01",
      CHAPELFLOW_USHER_01_PASSWORD: "private-password-01",
      CHAPELFLOW_USHER_02_USERNAME: "usher02",
      CHAPELFLOW_USHER_02_PASSWORD: "private-password-02",
    };
    await seedUshers(database, environment);
    await seedUshers(database, environment);
    const result = await database.query<{
      username: string;
      role: string;
      password_hash: string;
    }>("SELECT username, role, password_hash FROM users ORDER BY username");
    expect(result.rows).toHaveLength(2);
    expect(result.rows.every((row) => row.role === "attendance_usher")).toBe(
      true,
    );
    expect(
      result.rows.every(
        (row) =>
          row.password_hash.startsWith("scrypt$") &&
          !row.password_hash.includes("private-password"),
      ),
    ).toBe(true);

    const adminEnvironment = {
      CHAPELFLOW_ADMIN_USERNAME: "chapeladmin",
      CHAPELFLOW_ADMIN_EMAIL: "admin@example.edu.ng",
      CHAPELFLOW_ADMIN_NAME: "Chapel Administrator",
      CHAPELFLOW_ADMIN_PASSWORD: "private-admin-password",
    };
    await seedAdministrator(database, adminEnvironment);
    await seedAdministrator(database, adminEnvironment);
    const administrators = await database.query<{
      role: string;
      password_hash: string;
    }>("SELECT role, password_hash FROM users WHERE role = 'super_admin'");
    expect(administrators.rows).toHaveLength(1);
    expect(administrators.rows[0]?.password_hash).not.toContain(
      "private-admin-password",
    );
  }, 10_000);

  it("allows an embedded-development registration to sign in immediately", async () => {
    app = createApp(database, {
      ...config,
      NODE_ENV: "development",
      DATABASE_URL: "pglite://memory",
    });
    const registration = await request(app).post("/api/auth/register").send({
      email: "local.student@example.edu.ng",
      password: "secure-password-3",
      firstName: "Local",
      lastName: "Student",
      identifier: "CU/26/LOCAL",
      programme: "Computer Science",
      level: "200",
      unitCommunityId: registrationUnitId,
      fellowshipCommunityId: registrationFellowshipId,
      acceptedPolicies: true,
    });
    expect(registration.status).toBe(201);
    expect(registration.body.data.approvalRequired).toBe(false);

    const signIn = await request(app).post("/api/auth/login").send({
      identifier: "CU/26/LOCAL",
      password: "secure-password-3",
    });
    expect(signIn.status).toBe(200);
    expect(signIn.body.data.role).toBe("member");
    expect(signIn.headers["set-cookie"]).toBeDefined();
  });

  it("returns an authorized dashboard summary", async () => {
    await addUser({
      username: "dashboard-student",
      role: "member",
      student: { matric: "CU/26/DASH" },
    });
    const memberCookie = await login("dashboard-student");

    const dashboard = await request(app)
      .get("/api/dashboard?branchId=abeokuta-main")
      .set("Cookie", memberCookie);
    expect(dashboard.status).toBe(200);
    expect(dashboard.body.data.metrics).toHaveLength(4);
    expect(dashboard.body.data.attendanceTrend).toHaveLength(8);

    const anotherBranch = await request(app)
      .get("/api/dashboard?branchId=another-branch")
      .set("Cookie", memberCookie);
    expect(anotherBranch.status).toBe(403);
  });
});
