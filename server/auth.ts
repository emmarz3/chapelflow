import { randomUUID } from "node:crypto";
import { Router } from "express";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { inTransaction } from "./db.js";
import { ApiProblem, authenticate } from "./http.js";
import { permissionsFor, type Role } from "./permissions.js";
import {
  createOpaqueToken,
  hashPassword,
  hashToken,
  verifyPassword,
} from "./security.js";

const registrationSchema = z.object({
  email: z.string().trim().email().max(320),
  password: z
    .string()
    .min(8)
    .max(128)
    .regex(/\d/, "Password must include a number."),
  firstName: z.string().trim().min(1).max(80),
  lastName: z.string().trim().min(1).max(80),
  identifier: z.string().trim().min(3).max(80),
  programme: z.string().trim().max(160).optional().default(""),
  level: z.string().trim().max(40).optional().default(""),
  unitCommunityId: z.string().uuid(),
  fellowshipCommunityId: z.string().uuid(),
  acceptedPolicies: z.literal(true),
});

const loginSchema = z.object({
  identifier: z.string().trim().min(1).max(320),
  password: z.string().min(1).max(128),
});

const setupPasswordSchema = z.object({
  token: z.string().min(32).max(500),
  password: z
    .string()
    .min(8)
    .max(128)
    .regex(/\d/, "Password must include a number."),
});

const clientPermissions: Record<Role, string[]> = {
  super_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "attendance:scan",
    "attendance:manual",
    "events:read",
    "events:write",
    "finance:read",
    "finance:write",
    "communication:write",
    "workers:read",
    "workers:write",
    "workers:acknowledge",
    "assets:read",
    "assets:write",
    "media:write",
    "cms:write",
    "analytics:read",
    "branches:manage",
    "audit:read",
    "settings:manage",
    "community:view",
    "community:view_all",
    "community:manage",
    "leadership:view",
    "leadership:manage",
    "chapel:announce",
  ],
  chapel_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "attendance:scan",
    "attendance:manual",
    "events:read",
    "events:write",
    "finance:read",
    "finance:write",
    "communication:write",
    "workers:read",
    "workers:write",
    "workers:acknowledge",
    "assets:read",
    "assets:write",
    "media:write",
    "cms:write",
    "analytics:read",
    "audit:read",
  ],
  chaplain: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "communication:write",
    "analytics:read",
    "community:view",
    "community:view_all",
    "leadership:view",
    "chapel:announce",
  ],
  student_chaplain: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "communication:write",
    "community:view",
    "community:view_all",
    "leadership:view",
    "chapel:announce",
  ],
  treasurer: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "finance:read",
    "finance:write",
    "community:view",
    "leadership:view",
  ],
  chapel_official: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "community:view",
    "leadership:view",
  ],
  pastor: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "workers:read",
    "analytics:read",
    "media:write",
  ],
  worker: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "workers:read",
    "workers:acknowledge",
  ],
  attendance_usher: ["attendance:read", "attendance:scan", "attendance:manual"],
  member: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "community:view",
  ],
};

function toClientUser(
  user: { id: string; email: string; full_name: string; role: Role },
  roles: Role[] = [user.role],
) {
  const allRoles = Array.from(new Set([user.role, ...roles]));
  return {
    id: user.id,
    name: user.full_name,
    email: user.email,
    role: user.role,
    roles: allRoles,
    branchId: "abeokuta-main",
    branchName: "Abeokuta Main Chapel",
    permissions: Array.from(
      new Set(allRoles.flatMap((role) => clientPermissions[role])),
    ),
    initials: user.full_name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join(""),
  };
}

export function authRouter(database: Database, config: AppConfig) {
  const router = Router();

  router.post("/setup-password", async (request, response, next) => {
    try {
      const input = setupPasswordSchema.parse(request.body);
      await inTransaction(database, async (client) => {
        const setup = await client.query<{ id: string; user_id: string }>(
          `SELECT id, user_id FROM account_setup_tokens
            WHERE token_hash = $1 AND used_at IS NULL AND expires_at > NOW()
            LIMIT 1 FOR UPDATE`,
          [hashToken(input.token, config.CHAPELFLOW_SESSION_SECRET)],
        );
        if (!setup.rows[0])
          throw new ApiProblem(
            400,
            "SETUP_LINK_INVALID",
            "The account setup link is invalid or expired.",
          );
        await client.query(
          "UPDATE users SET password_hash = $1, status = 'active', updated_at = NOW() WHERE id = $2",
          [await hashPassword(input.password), setup.rows[0].user_id],
        );
        await client.query(
          "UPDATE account_setup_tokens SET used_at = NOW() WHERE id = $1",
          [setup.rows[0].id],
        );
        await client.query("DELETE FROM auth_sessions WHERE user_id = $1", [
          setup.rows[0].user_id,
        ]);
      });
      response.status(204).end();
    } catch (error) {
      if (error instanceof z.ZodError)
        return next(
          new ApiProblem(422, "VALIDATION_ERROR", "Choose a valid password."),
        );
      next(error);
    }
  });

  router.post("/register", async (request, response, next) => {
    try {
      const parsed = registrationSchema.safeParse(request.body);
      if (!parsed.success)
        throw new ApiProblem(
          422,
          "VALIDATION_ERROR",
          "Check the registration details.",
          z.flattenError(parsed.error).fieldErrors,
        );
      const input = parsed.data;
      const email = input.email.toLowerCase();
      const username = input.identifier.toLowerCase();
      const passwordHash = await hashPassword(input.password);
      const autoApprove =
        config.NODE_ENV === "development" &&
        config.DATABASE_URL.startsWith("pglite://");
      await inTransaction(database, async (client) => {
        const selected = await client.query<{
          id: string;
          type: "unit" | "campus_fellowship";
          requires_approval: boolean;
        }>(
          `SELECT id, type, requires_approval FROM communities
            WHERE id IN ($1, $2) AND status = 'active'`,
          [input.unitCommunityId, input.fellowshipCommunityId],
        );
        const unit = selected.rows.find(
          (community) =>
            community.id === input.unitCommunityId && community.type === "unit",
        );
        const fellowship = selected.rows.find(
          (community) =>
            community.id === input.fellowshipCommunityId &&
            community.type === "campus_fellowship",
        );
        if (!unit || !fellowship) {
          throw new ApiProblem(
            422,
            "INVALID_COMMUNITY",
            "Select a valid chapel unit and campus fellowship.",
          );
        }
        const userId = randomUUID();
        await client.query(
          `INSERT INTO users (id, username, email, password_hash, full_name, role, status)
           VALUES ($1, $2, $3, $4, $5, 'member', $6)`,
          [
            userId,
            username,
            email,
            passwordHash,
            `${input.firstName} ${input.lastName}`,
            autoApprove ? "active" : "inactive",
          ],
        );
        for (const community of [unit, fellowship]) {
          const membershipStatus = community.requires_approval
            ? "pending"
            : "active";
          await client.query(
            `INSERT INTO community_memberships
              (id, community_id, user_id, status, is_primary, approved_at)
             VALUES ($1, $2, $3, $4, TRUE, CASE WHEN $4 = 'active' THEN NOW() ELSE NULL END)`,
            [randomUUID(), community.id, userId, membershipStatus],
          );
        }
        await client.query(
          `INSERT INTO students
            (id, user_id, matric_number, programme, academic_level, qr_pass_id, pass_status, approval_status)
           VALUES ($1, $2, $3, $4, $5, $6, 'active', $7)`,
          [
            randomUUID(),
            userId,
            input.identifier,
            input.programme || null,
            input.level || null,
            randomUUID(),
            autoApprove ? "approved" : "pending",
          ],
        );
        await client.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'account.registered', 'user', $2)`,
          [randomUUID(), userId],
        );
      });
      response.status(201).json({
        data: { verificationRequired: false, approvalRequired: !autoApprove },
      });
    } catch (error) {
      if (
        typeof error === "object" &&
        error &&
        "code" in error &&
        error.code === "23505"
      ) {
        return next(
          new ApiProblem(
            409,
            "ACCOUNT_EXISTS",
            "An account already uses that email or identifier.",
          ),
        );
      }
      next(error);
    }
  });

  router.post("/login", async (request, response, next) => {
    try {
      const input = loginSchema.parse(request.body);
      const result = await database.query<{
        id: string;
        email: string;
        full_name: string;
        role: Role;
        password_hash: string;
      }>(
        `SELECT DISTINCT u.id, u.email, u.full_name, u.role, u.password_hash
           FROM users u LEFT JOIN students st ON st.user_id = u.id
          WHERE (u.username = $1 OR u.email = $1 OR LOWER(st.matric_number) = $1)
            AND u.status = 'active' LIMIT 1`,
        [input.identifier.toLowerCase()],
      );
      const user = result.rows[0];
      if (
        !user ||
        !(await verifyPassword(input.password, user.password_hash))
      ) {
        throw new ApiProblem(
          401,
          "INVALID_CREDENTIALS",
          "The identifier or password is incorrect.",
        );
      }
      const token = createOpaqueToken();
      await database.query(
        `INSERT INTO auth_sessions (id, user_id, token_hash, expires_at)
         VALUES ($1, $2, $3, NOW() + INTERVAL '12 hours')`,
        [
          randomUUID(),
          user.id,
          hashToken(token, config.CHAPELFLOW_SESSION_SECRET),
        ],
      );
      const roleRows = await database.query<{ role_key: Role }>(
        "SELECT role_key FROM user_global_roles WHERE user_id = $1",
        [user.id],
      );
      response.cookie("chapelflow_session", token, {
        httpOnly: true,
        secure: config.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 12 * 60 * 60 * 1000,
        path: "/",
      });
      response.json({
        data: toClientUser(
          user,
          roleRows.rows.map((row) => row.role_key),
        ),
      });
    } catch (error) {
      if (error instanceof z.ZodError)
        return next(
          new ApiProblem(422, "VALIDATION_ERROR", "Check the sign-in details."),
        );
      next(error);
    }
  });

  router.get("/me", authenticate(database, config), (request, response) => {
    response.json({
      data: toClientUser(
        {
          id: request.authUser!.id,
          email: request.authUser!.email,
          full_name: request.authUser!.name,
          role: request.authUser!.role,
        },
        request.authUser!.roles,
      ),
    });
  });

  router.post(
    "/logout",
    authenticate(database, config),
    async (request, response, next) => {
      try {
        await database.query(
          "DELETE FROM auth_sessions WHERE token_hash = $1",
          [
            hashToken(
              request.authSessionToken!,
              config.CHAPELFLOW_SESSION_SECRET,
            ),
          ],
        );
        response.clearCookie("chapelflow_session", { path: "/" });
        response.status(204).end();
      } catch (error) {
        next(error);
      }
    },
  );

  return router;
}

export { permissionsFor };
