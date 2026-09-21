// @vitest-environment node
import { randomUUID } from "node:crypto";
import { newDb } from "pg-mem";
import request from "supertest";
import { beforeEach, describe, expect, it } from "vitest";
import { createApp } from "./app.js";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { runMigrations } from "./migrations.js";
import {
  organizationCommunities,
  seedOrganization,
} from "./organization-seed.js";
import { hashPassword } from "./security.js";

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
let musicId: string;
let loveId: string;
let truthId: string;

async function addUser(username: string, role = "member") {
  const id = randomUUID();
  const globalOnly = [
    "chaplain",
    "student_chaplain",
    "treasurer",
    "chapel_official",
  ].includes(role);
  await database.query(
    `INSERT INTO users (id, username, email, password_hash, full_name, role, status)
     VALUES ($1, $2, $3, $4, $5, $6, 'active')`,
    [
      id,
      username,
      `${username}@example.edu.ng`,
      await hashPassword("secure-password-1"),
      username,
      globalOnly ? "member" : role,
    ],
  );
  if (globalOnly) {
    await database.query(
      "INSERT INTO user_global_roles (id, user_id, role_key) VALUES ($1, $2, $3)",
      [randomUUID(), id, role],
    );
  }
  return id;
}

async function login(username: string) {
  const response = await request(app)
    .post("/api/auth/login")
    .send({ identifier: username, password: "secure-password-1" });
  expect(response.status).toBe(200);
  return response.headers["set-cookie"] as unknown as string[];
}

async function membership(
  userId: string,
  communityId: string,
  status = "active",
) {
  await database.query(
    `INSERT INTO community_memberships
      (id, community_id, user_id, status, approved_at)
     VALUES ($1, $2, $3, $4, CASE WHEN $4 = 'active' THEN NOW() ELSE NULL END)`,
    [randomUUID(), communityId, userId, status],
  );
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
  const communities = await database.query<{ id: string; slug: string }>(
    "SELECT id, slug FROM communities",
  );
  musicId = communities.rows.find((row) => row.slug === "music")!.id;
  loveId = communities.rows.find(
    (row) => row.slug === "love-campus-fellowship",
  )!.id;
  truthId = communities.rows.find(
    (row) => row.slug === "truth-campus-fellowship",
  )!.id;
  app = createApp(database, config);
});

describe("community engine", () => {
  it("creates validated unit and fellowship memberships during registration", async () => {
    const registration = await request(app).post("/api/auth/register").send({
      email: "community.student@example.edu.ng",
      password: "secure-password-2",
      firstName: "Community",
      lastName: "Student",
      identifier: "CU/26/COM/01",
      programme: "Computer Science",
      level: "200",
      unitCommunityId: musicId,
      fellowshipCommunityId: loveId,
      acceptedPolicies: true,
    });
    expect(registration.status).toBe(201);
    const rows = await database.query<{ type: string; status: string }>(
      `SELECT c.type, cm.status FROM community_memberships cm
       JOIN communities c ON c.id = cm.community_id
       JOIN users u ON u.id = cm.user_id WHERE u.email = $1 ORDER BY c.type`,
      ["community.student@example.edu.ng"],
    );
    expect(rows.rows).toEqual([
      { type: "campus_fellowship", status: "pending" },
      { type: "unit", status: "pending" },
    ]);
  });

  it("rejects invalid or type-swapped community registration selections", async () => {
    const payload = {
      email: "invalid.community@example.edu.ng",
      password: "secure-password-2",
      firstName: "Invalid",
      lastName: "Selection",
      identifier: "CU/26/COM/02",
      programme: "Law",
      level: "100",
      unitCommunityId: loveId,
      fellowshipCommunityId: musicId,
      acceptedPolicies: true,
    };
    const response = await request(app)
      .post("/api/auth/register")
      .send(payload);
    expect(response.status).toBe(422);
    expect(response.body.code).toBe("INVALID_COMMUNITY");
  });

  it("blocks pending members and outsiders from private workspace and message IDs", async () => {
    const pendingId = await addUser("pending-member");
    const outsiderId = await addUser("outsider");
    await membership(pendingId, musicId, "pending");
    await membership(outsiderId, truthId);
    const pendingCookie = await login("pending-member");
    const outsiderCookie = await login("outsider");
    const pending = await request(app)
      .get("/api/communities/music")
      .set("Cookie", pendingCookie);
    expect(pending.status).toBe(403);
    expect(pending.body.code).toBe("MEMBERSHIP_PENDING");
    expect(
      (
        await request(app)
          .get("/api/communities/music/messages")
          .set("Cookie", outsiderCookie)
      ).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .get(`/api/communities/${musicId}/messages`)
          .set("Cookie", outsiderCookie)
      ).status,
    ).toBe(403);
  });

  it("allows active members to read, post, search, and clear unread counts", async () => {
    const memberId = await addUser("music-member");
    await membership(memberId, musicId);
    const cookie = await login("music-member");
    expect(
      (await request(app).get("/api/communities/music").set("Cookie", cookie))
        .status,
    ).toBe(200);
    const posted = await request(app)
      .post("/api/communities/music/messages")
      .set("Cookie", cookie)
      .send({ body: "Friday rehearsal is confirmed." });
    expect(posted.status).toBe(201);
    const search = await request(app)
      .get("/api/communities/music/messages?search=rehearsal")
      .set("Cookie", cookie);
    expect(search.body.data).toHaveLength(1);
    const beforeRead = await request(app)
      .get("/api/communities")
      .set("Cookie", cookie);
    expect(beforeRead.body.data[0].unreadCount).toBe(1);
    expect(
      (
        await request(app)
          .post("/api/communities/music/read")
          .set("Cookie", cookie)
      ).status,
    ).toBe(204);
    const afterRead = await request(app)
      .get("/api/communities")
      .set("Cookie", cookie);
    expect(afterRead.body.data[0].unreadCount).toBe(0);
  });

  it("enforces broadcast-only chat while retaining leader privileges only in scope", async () => {
    const memberId = await addUser("broadcast-member");
    const leaderId = await addUser("music-leader");
    await membership(memberId, musicId);
    await membership(leaderId, musicId);
    await database.query(
      "UPDATE communities SET members_can_post = FALSE WHERE id = $1",
      [musicId],
    );
    await database.query(
      `UPDATE leadership_assignments SET user_id = $1
        WHERE community_id = $2 AND position_id IN
          (SELECT id FROM leadership_positions WHERE name = 'Head of Music') AND active = TRUE`,
      [leaderId, musicId],
    );
    const memberCookie = await login("broadcast-member");
    const leaderCookie = await login("music-leader");
    expect(
      (
        await request(app)
          .post("/api/communities/music/messages")
          .set("Cookie", memberCookie)
          .send({ body: "Member post" })
      ).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .post("/api/communities/music/messages")
          .set("Cookie", leaderCookie)
          .send({ body: "Leader post" })
      ).status,
    ).toBe(201);
    expect(
      (
        await request(app)
          .post("/api/communities/truth-campus-fellowship/announcements")
          .set("Cookie", leaderCookie)
          .send({ title: "Wrong scope", content: "Should fail" })
      ).status,
    ).toBe(403);
    const loginResponse = await request(app)
      .post("/api/auth/login")
      .send({ identifier: "music-leader", password: "secure-password-1" });
    expect(loginResponse.body.data.roles).toEqual(["member"]);
  });

  it("lets scoped leaders announce, moderate, schedule, and approve only their community", async () => {
    const leaderId = await addUser("full-leader");
    const pendingId = await addUser("approval-request");
    await membership(leaderId, musicId);
    await membership(pendingId, musicId, "pending");
    await database.query(
      `UPDATE leadership_assignments SET user_id = $1
        WHERE community_id = $2 AND position_id IN
          (SELECT id FROM leadership_positions WHERE name = 'Head of Music') AND active = TRUE`,
      [leaderId, musicId],
    );
    const cookie = await login("full-leader");
    const announcement = await request(app)
      .post("/api/communities/music/announcements")
      .set("Cookie", cookie)
      .send({
        title: "Choir rehearsal",
        content: "Arrive by 5 PM.",
        priority: "important",
      });
    expect(announcement.status).toBe(201);
    const event = await request(app)
      .post("/api/communities/music/events")
      .set("Cookie", cookie)
      .send({
        title: "Friday rehearsal",
        description: "Full team rehearsal",
        venue: "University Chapel",
        startsAt: "2027-01-08T17:00:00.000Z",
        endsAt: "2027-01-08T19:00:00.000Z",
      });
    expect(event.status).toBe(201);
    const pending = await request(app)
      .get("/api/communities/music/members?status=pending")
      .set("Cookie", cookie);
    expect(pending.body.data).toHaveLength(1);
    expect(
      (
        await request(app)
          .patch(`/api/communities/music/members/${pending.body.data[0].id}`)
          .set("Cookie", cookie)
          .send({ status: "active" })
      ).status,
    ).toBe(200);
  });

  it("gives Super Admin global management while Chaplain and Student Chaplain receive oversight without technical administration", async () => {
    await addUser("super", "super_admin");
    await addUser("chaplain", "chaplain");
    await addUser("student-chaplain", "student_chaplain");
    const superCookie = await login("super");
    const chaplainCookie = await login("chaplain");
    const studentCookie = await login("student-chaplain");
    expect(
      (
        await request(app)
          .get("/api/admin/communities")
          .set("Cookie", superCookie)
      ).status,
    ).toBe(200);
    expect(
      (
        await request(app)
          .get("/api/communities/music")
          .set("Cookie", chaplainCookie)
      ).status,
    ).toBe(200);
    expect(
      (
        await request(app)
          .get("/api/communities/music")
          .set("Cookie", studentCookie)
      ).status,
    ).toBe(200);
    expect(
      (
        await request(app)
          .get("/api/admin/communities")
          .set("Cookie", chaplainCookie)
      ).status,
    ).toBe(403);
    expect(
      (
        await request(app)
          .post("/api/chapel-announcements")
          .set("Cookie", studentCookie)
          .send({ title: "Thursday chapel", content: "Chapel starts at 9 AM." })
      ).status,
    ).toBe(201);
  });

  it("transfers leadership, preserves history, and revokes the previous leader's elevated access", async () => {
    const adminId = await addUser("transfer-admin", "super_admin");
    const previousId = await addUser("previous-leader");
    const nextId = await addUser("next-leader");
    await membership(previousId, musicId);
    await membership(nextId, musicId);
    const position = await database.query<{ id: string }>(
      "SELECT id FROM leadership_positions WHERE name = 'Head of Music'",
    );
    await database.query(
      "UPDATE leadership_assignments SET user_id = $1 WHERE position_id = $2 AND community_id = $3 AND active = TRUE",
      [previousId, position.rows[0]!.id, musicId],
    );
    const adminCookie = await login("transfer-admin");
    const previousCookie = await login("previous-leader");
    const transfer = await request(app)
      .post("/api/admin/leadership/assign")
      .set("Cookie", adminCookie)
      .send({
        positionId: position.rows[0]!.id,
        userId: nextId,
        communityId: musicId,
      });
    expect(transfer.status).toBe(201);
    expect(
      (
        await request(app)
          .post("/api/communities/music/announcements")
          .set("Cookie", previousCookie)
          .send({ title: "Former leader", content: "Should fail" })
      ).status,
    ).toBe(403);
    const history = await database.query<{ active: boolean }>(
      "SELECT active FROM leadership_assignments WHERE position_id = $1 ORDER BY created_at",
      [position.rows[0]!.id],
    );
    expect(history.rows.map((row) => row.active)).toEqual([false, true]);
    expect(adminId).toBeTruthy();
  });

  it("prevents duplicate membership, suspends access immediately, and blocks inactive communities", async () => {
    const userId = await addUser("suspended-member");
    await membership(userId, musicId);
    await expect(membership(userId, musicId)).rejects.toMatchObject({
      code: "23505",
    });
    const cookie = await login("suspended-member");
    await database.query(
      "UPDATE community_memberships SET status = 'suspended' WHERE user_id = $1 AND community_id = $2",
      [userId, musicId],
    );
    expect(
      (await request(app).get("/api/communities/music").set("Cookie", cookie))
        .status,
    ).toBe(403);
    await database.query(
      "UPDATE community_memberships SET status = 'active' WHERE user_id = $1 AND community_id = $2",
      [userId, musicId],
    );
    await database.query(
      "UPDATE communities SET status = 'inactive' WHERE id = $1",
      [musicId],
    );
    expect(
      (await request(app).get("/api/communities/music").set("Cookie", cookie))
        .status,
    ).toBe(403);
  });

  it("rejects message XSS and unauthenticated realtime subscriptions", async () => {
    const userId = await addUser("safe-member");
    await membership(userId, musicId);
    const cookie = await login("safe-member");
    const response = await request(app)
      .post("/api/communities/music/messages")
      .set("Cookie", cookie)
      .send({ body: "<script>alert('xss')</script>" });
    expect(response.status).toBe(422);
    expect(
      (await request(app).get("/api/communities/music/stream")).status,
    ).toBe(401);
  });

  it("seeds all supplied organization data idempotently and keeps the unnamed office vacant", async () => {
    await seedOrganization(database);
    const communities = await database.query<{ count: string }>(
      "SELECT COUNT(*)::text AS count FROM communities",
    );
    expect(Number(communities.rows[0]?.count)).toBe(
      organizationCommunities.length,
    );
    const vacant = await database.query<{ assignment_count: string }>(
      `SELECT COUNT(la.id)::text AS assignment_count FROM leadership_positions lp
       LEFT JOIN leadership_assignments la ON la.position_id = lp.id AND la.active = TRUE
       WHERE lp.name = 'Female Hostel Fellowship Coordinator 2'`,
    );
    expect(Number(vacant.rows[0]?.assignment_count)).toBe(0);
  });

  it("provisions leader accounts without plaintext passwords and activates a one-time setup token", async () => {
    await addUser("account-admin", "super_admin");
    const adminCookie = await login("account-admin");
    const created = await request(app)
      .post("/api/admin/accounts")
      .set("Cookie", adminCookie)
      .send({
        username: "new.leader",
        email: "new.leader@example.edu.ng",
        name: "New Community Leader",
        primaryRole: "member",
        globalRoles: [],
      });
    expect(created.status).toBe(201);
    const token = String(created.body.data.setupPath).split("setup=")[1];
    const stored = await database.query<{
      password_hash: string;
      status: string;
    }>("SELECT password_hash, status FROM users WHERE username = 'new.leader'");
    expect(stored.rows[0]?.password_hash).not.toContain(
      "secure-leader-password-1",
    );
    expect(stored.rows[0]?.status).toBe("inactive");
    expect(
      (
        await request(app)
          .post("/api/auth/setup-password")
          .send({ token, password: "secure-leader-password-1" })
      ).status,
    ).toBe(204);
    expect(
      (
        await request(app)
          .post("/api/auth/setup-password")
          .send({ token, password: "another-password-1" })
      ).status,
    ).toBe(400);
    expect(
      (
        await request(app)
          .post("/api/auth/login")
          .send({
            identifier: "new.leader",
            password: "secure-leader-password-1",
          })
      ).status,
    ).toBe(200);
  });
});
