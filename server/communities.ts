import { EventEmitter } from "node:events";
import { randomUUID } from "node:crypto";
import {
  Router,
  type NextFunction,
  type Request,
  type Response,
} from "express";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Database, DatabaseClient } from "./db.js";
import { inTransaction } from "./db.js";
import { ApiProblem, authenticate, requirePermission } from "./http.js";
import { rolesHavePermission, roles } from "./permissions.js";
import { createOpaqueToken, hashPassword, hashToken } from "./security.js";

const communityEvents = new EventEmitter();
communityEvents.setMaxListeners(500);

const plainText = (max: number) =>
  z
    .string()
    .trim()
    .min(1)
    .max(max)
    .refine((value) => !/<\/?[a-z][^>]*>/i.test(value), "HTML is not allowed.");

const messageSchema = z.object({
  body: plainText(4000),
  replyToId: z.string().uuid().nullable().optional(),
});

const announcementSchema = z.object({
  title: plainText(180),
  content: plainText(10_000),
  pinned: z.boolean().default(false),
  priority: z.enum(["normal", "important", "urgent"]).default("normal"),
  expiresAt: z.string().datetime().nullable().optional(),
});

const eventSchema = z
  .object({
    title: plainText(180),
    description: z.string().trim().max(10_000).default(""),
    venue: plainText(240),
    startsAt: z.string().datetime(),
    endsAt: z.string().datetime(),
  })
  .refine((value) => new Date(value.endsAt) > new Date(value.startsAt), {
    message: "The event must end after it starts.",
    path: ["endsAt"],
  });

type CommunityRow = {
  id: string;
  name: string;
  slug: string;
  type: "unit" | "campus_fellowship" | "hostel_fellowship" | "other";
  description: string;
  status: "active" | "inactive";
  requires_approval: boolean;
  members_can_post: boolean;
  chat_enabled: boolean;
};

type CommunityAccess = {
  community: CommunityRow;
  membershipStatus: string | null;
  isLeader: boolean;
  canRead: boolean;
  canPost: boolean;
  canManage: boolean;
};

async function resolveAccess(
  database: Database | DatabaseClient,
  request: Request,
  slugOrId: string,
): Promise<CommunityAccess> {
  const result = await database.query<CommunityRow>(
    `SELECT id, name, slug, type, description, status,
            requires_approval, members_can_post, chat_enabled
       FROM communities WHERE slug = $1 OR id::text = $1 LIMIT 1`,
    [slugOrId],
  );
  const community = result.rows[0];
  if (!community)
    throw new ApiProblem(
      404,
      "COMMUNITY_NOT_FOUND",
      "The community does not exist.",
    );
  const membership = await database.query<{ status: string }>(
    `SELECT status FROM community_memberships
      WHERE community_id = $1 AND user_id = $2 LIMIT 1`,
    [community.id, request.authUser!.id],
  );
  const leadership = await database.query(
    `SELECT 1 FROM leadership_assignments
      WHERE community_id = $1 AND user_id = $2 AND active = TRUE
        AND (ends_at IS NULL OR ends_at > NOW()) LIMIT 1`,
    [community.id, request.authUser!.id],
  );
  const membershipStatus = membership.rows[0]?.status ?? null;
  const isLeader = Boolean(leadership.rows.length);
  const canViewAll = rolesHavePermission(
    request.authUser!.roles,
    "community:view_all",
  );
  const canManageAll = rolesHavePermission(
    request.authUser!.roles,
    "community:manage",
  );
  const canRead =
    community.status === "active" &&
    (canViewAll || isLeader || membershipStatus === "active");
  return {
    community,
    membershipStatus,
    isLeader,
    canRead,
    canManage: canManageAll || isLeader,
    canPost:
      community.chat_enabled &&
      (canManageAll ||
        isLeader ||
        (membershipStatus === "active" && community.members_can_post)),
  };
}

function requireCommunityAccess(
  database: Database,
  capability: "read" | "post" | "manage",
) {
  return async (request: Request, response: Response, next: NextFunction) => {
    try {
      const access = await resolveAccess(
        database,
        request,
        String(request.params.slug),
      );
      const allowed =
        capability === "read"
          ? access.canRead
          : capability === "post"
            ? access.canPost
            : access.canManage;
      if (!allowed) {
        throw new ApiProblem(
          403,
          access.membershipStatus === "pending"
            ? "MEMBERSHIP_PENDING"
            : "COMMUNITY_ACCESS_DENIED",
          access.membershipStatus === "pending"
            ? "Your membership is awaiting approval."
            : "You do not have access to this community.",
        );
      }
      response.locals.communityAccess = access;
      next();
    } catch (error) {
      next(error);
    }
  };
}

async function notifyCommunityMembers(
  client: DatabaseClient,
  communityId: string,
  input: {
    type: string;
    title: string;
    body: string;
    href: string;
    exceptUserId?: string;
  },
) {
  const members = await client.query<{ user_id: string }>(
    `SELECT user_id FROM community_memberships
      WHERE community_id = $1 AND status = 'active'`,
    [communityId],
  );
  for (const member of members.rows) {
    if (member.user_id === input.exceptUserId) continue;
    await client.query(
      `INSERT INTO notifications
        (id, user_id, community_id, type, title, body, href)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        randomUUID(),
        member.user_id,
        communityId,
        input.type,
        input.title,
        input.body,
        input.href,
      ],
    );
  }
}

export function publicCommunitiesRouter(database: Database) {
  const router = Router();
  router.get("/", async (request, response, next) => {
    try {
      const type = z
        .enum(["unit", "campus_fellowship", "hostel_fellowship", "other"])
        .optional()
        .parse(request.query.type);
      const result = await database.query<CommunityRow>(
        `SELECT id, name, slug, type, description, status,
                requires_approval, members_can_post, chat_enabled
           FROM communities
          WHERE status = 'active' AND ($1::text IS NULL OR type = $1)
          ORDER BY type, name`,
        [type ?? null],
      );
      response.json({ data: result.rows });
    } catch (error) {
      next(error);
    }
  });
  return router;
}

export function communitiesRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));
  router.use(requirePermission("community:view"));

  router.get("/", async (request, response, next) => {
    try {
      const viewAll = rolesHavePermission(
        request.authUser!.roles,
        "community:view_all",
      );
      const [allCommunities, memberships, leadership] = await Promise.all([
        database.query<CommunityRow>(
          "SELECT * FROM communities WHERE status = 'active' ORDER BY type, name",
        ),
        database.query<{ community_id: string; status: string }>(
          "SELECT community_id, status FROM community_memberships WHERE user_id = $1",
          [request.authUser!.id],
        ),
        database.query<{ community_id: string }>(
          `SELECT community_id FROM leadership_assignments
            WHERE user_id = $1 AND active = TRUE AND community_id IS NOT NULL`,
          [request.authUser!.id],
        ),
      ]);
      const membershipByCommunity = new Map(
        memberships.rows.map((row) => [row.community_id, row.status]),
      );
      const ledCommunities = new Set(
        leadership.rows.map((row) => row.community_id),
      );
      const result = allCommunities.rows
        .filter(
          (community) =>
            viewAll ||
            membershipByCommunity.has(community.id) ||
            ledCommunities.has(community.id),
        )
        .map((community) => ({
          ...community,
          membership_status: membershipByCommunity.get(community.id) ?? null,
          is_leader: ledCommunities.has(community.id),
        }));
      const data = [];
      for (const community of result) {
        const unread = await database.query<{ count: string }>(
          `SELECT COUNT(m.id)::text AS count
             FROM conversations c
             JOIN messages m ON m.conversation_id = c.id AND m.deleted_at IS NULL
             LEFT JOIN conversation_read_states rs ON rs.conversation_id = c.id AND rs.user_id = $2
            WHERE c.community_id = $1 AND m.created_at > COALESCE(rs.last_read_at, '1970-01-01'::timestamptz)`,
          [community.id, request.authUser!.id],
        );
        data.push({
          ...community,
          unreadCount: Number(unread.rows[0]?.count ?? 0),
        });
      }
      response.json({ data });
    } catch (error) {
      next(error);
    }
  });

  router.get("/leadership/directory", async (_request, response, next) => {
    try {
      const result = await database.query(
        `SELECT lp.name AS position, la.assignee_name,
                COALESCE(u.full_name, la.assignee_name) AS leader_name,
                c.name AS community_name, c.slug AS community_slug, c.type AS community_type,
                la.starts_at, la.ends_at
           FROM leadership_positions lp
           LEFT JOIN leadership_assignments la ON la.position_id = lp.id AND la.active = TRUE
           LEFT JOIN users u ON u.id = la.user_id
           LEFT JOIN communities c ON c.id = la.community_id
          ORDER BY c.type NULLS FIRST, c.name NULLS FIRST, lp.name`,
      );
      response.json({ data: result.rows });
    } catch (error) {
      next(error);
    }
  });

  router.get(
    "/:slug",
    requireCommunityAccess(database, "read"),
    async (_request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        const [leaders, memberCount, announcement, nextEvent] =
          await Promise.all([
            database.query(
              `SELECT lp.name AS position, COALESCE(u.full_name, la.assignee_name) AS name
             FROM leadership_assignments la JOIN leadership_positions lp ON lp.id = la.position_id
             LEFT JOIN users u ON u.id = la.user_id
            WHERE la.community_id = $1 AND la.active = TRUE ORDER BY lp.name`,
              [access.community.id],
            ),
            database.query<{ count: string }>(
              "SELECT COUNT(*)::text AS count FROM community_memberships WHERE community_id = $1 AND status = 'active'",
              [access.community.id],
            ),
            database.query(
              `SELECT a.id, a.title, a.content, a.priority, a.pinned, a.published_at,
                  u.full_name AS author_name
             FROM announcements a JOIN users u ON u.id = a.author_id
            WHERE a.community_id = $1 AND a.published_at <= NOW()
              AND (a.expires_at IS NULL OR a.expires_at > NOW())
            ORDER BY a.pinned DESC, a.published_at DESC LIMIT 1`,
              [access.community.id],
            ),
            database.query(
              `SELECT id, title, description, venue, starts_at, ends_at, status
             FROM community_events
            WHERE community_id = $1 AND status = 'upcoming' AND starts_at > NOW()
            ORDER BY starts_at LIMIT 1`,
              [access.community.id],
            ),
          ]);
        response.json({
          data: {
            ...access.community,
            membershipStatus: access.membershipStatus,
            access: {
              isLeader: access.isLeader,
              canPost: access.canPost,
              canManage: access.canManage,
            },
            leaders: leaders.rows,
            memberCount: Number(memberCount.rows[0]?.count ?? 0),
            pinnedAnnouncement: announcement.rows[0] ?? null,
            nextEvent: nextEvent.rows[0] ?? null,
          },
        });
      } catch (error) {
        next(error);
      }
    },
  );

  router.get(
    "/:slug/messages",
    requireCommunityAccess(database, "read"),
    async (request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        const before = z
          .string()
          .datetime()
          .optional()
          .parse(request.query.before);
        const search = z
          .string()
          .trim()
          .max(100)
          .optional()
          .parse(request.query.search);
        const result = await database.query(
          `SELECT m.id, m.body, m.reply_to_id, m.pinned, m.created_at, m.edited_at,
                u.id AS sender_id, u.full_name AS sender_name
           FROM messages m
           JOIN conversations c ON c.id = m.conversation_id
           JOIN users u ON u.id = m.sender_id
          WHERE c.community_id = $1 AND m.deleted_at IS NULL
            AND ($2::timestamptz IS NULL OR m.created_at < $2)
            AND ($3::text IS NULL OR m.body ILIKE '%' || $3 || '%')
          ORDER BY m.created_at DESC LIMIT 50`,
          [access.community.id, before ?? null, search ?? null],
        );
        response.json({ data: result.rows.reverse() });
      } catch (error) {
        next(error);
      }
    },
  );

  router.post(
    "/:slug/messages",
    requireCommunityAccess(database, "post"),
    async (request, response, next) => {
      try {
        const input = messageSchema.parse(request.body);
        const access = response.locals.communityAccess as CommunityAccess;
        const conversation = await database.query<{ id: string }>(
          "SELECT id FROM conversations WHERE community_id = $1 AND type = 'community'",
          [access.community.id],
        );
        if (input.replyToId) {
          const reply = await database.query(
            `SELECT 1 FROM messages m JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = $1 AND c.community_id = $2 AND m.deleted_at IS NULL`,
            [input.replyToId, access.community.id],
          );
          if (!reply.rows.length)
            throw new ApiProblem(
              422,
              "INVALID_REPLY",
              "The replied-to message is unavailable.",
            );
        }
        const id = randomUUID();
        const inserted = await database.query(
          `INSERT INTO messages (id, conversation_id, sender_id, body, reply_to_id)
         VALUES ($1, $2, $3, $4, $5)
         RETURNING id, body, reply_to_id, pinned, created_at`,
          [
            id,
            conversation.rows[0]!.id,
            request.authUser!.id,
            input.body,
            input.replyToId ?? null,
          ],
        );
        communityEvents.emit(access.community.id, {
          type: "message.created",
          data: inserted.rows[0],
        });
        response.status(201).json({
          data: {
            ...inserted.rows[0],
            senderId: request.authUser!.id,
            senderName: request.authUser!.name,
          },
        });
      } catch (error) {
        if (error instanceof z.ZodError)
          return next(
            new ApiProblem(
              422,
              "VALIDATION_ERROR",
              "Check the message.",
              z.flattenError(error).fieldErrors,
            ),
          );
        next(error);
      }
    },
  );

  router.delete(
    "/:slug/messages/:messageId",
    requireCommunityAccess(database, "manage"),
    async (request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        const updated = await database.query<{ id: string }>(
          `UPDATE messages SET deleted_at = NOW()
          WHERE id = $1 AND conversation_id IN (SELECT id FROM conversations WHERE community_id = $2)
            AND deleted_at IS NULL RETURNING id`,
          [request.params.messageId, access.community.id],
        );
        if (!updated.rows.length)
          throw new ApiProblem(
            404,
            "MESSAGE_NOT_FOUND",
            "The message does not exist.",
          );
        await database.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
         VALUES ($1, $2, 'community.message_moderated', 'message', $3)`,
          [randomUUID(), request.authUser!.id, request.params.messageId],
        );
        response.status(204).end();
      } catch (error) {
        next(error);
      }
    },
  );

  router.post(
    "/:slug/read",
    requireCommunityAccess(database, "read"),
    async (request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        await database.query(
          `INSERT INTO conversation_read_states (conversation_id, user_id, last_read_at)
         SELECT id, $2, NOW() FROM conversations WHERE community_id = $1 AND type = 'community'
         ON CONFLICT (conversation_id, user_id) DO UPDATE SET last_read_at = NOW()`,
          [access.community.id, request.authUser!.id],
        );
        response.status(204).end();
      } catch (error) {
        next(error);
      }
    },
  );

  router.get(
    "/:slug/announcements",
    requireCommunityAccess(database, "read"),
    async (_request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        const result = await database.query(
          `SELECT a.id, a.title, a.content, a.pinned, a.priority, a.published_at,
                a.expires_at, u.full_name AS author_name
           FROM announcements a JOIN users u ON u.id = a.author_id
          WHERE a.community_id = $1 AND a.published_at <= NOW()
            AND (a.expires_at IS NULL OR a.expires_at > NOW())
          ORDER BY a.pinned DESC, a.published_at DESC`,
          [access.community.id],
        );
        response.json({ data: result.rows });
      } catch (error) {
        next(error);
      }
    },
  );

  router.post(
    "/:slug/announcements",
    requireCommunityAccess(database, "manage"),
    async (request, response, next) => {
      try {
        const input = announcementSchema.parse(request.body);
        const access = response.locals.communityAccess as CommunityAccess;
        const id = randomUUID();
        await inTransaction(database, async (client) => {
          await client.query(
            `INSERT INTO announcements
            (id, community_id, author_id, title, content, pinned, priority, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
            [
              id,
              access.community.id,
              request.authUser!.id,
              input.title,
              input.content,
              input.pinned,
              input.priority,
              input.expiresAt ?? null,
            ],
          );
          await notifyCommunityMembers(client, access.community.id, {
            type: "community.announcement",
            title: access.community.name,
            body: input.title,
            href: `/app/communities/${access.community.slug}?tab=announcements`,
            exceptUserId: request.authUser!.id,
          });
          await client.query(
            `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'community.announcement_created', 'announcement', $3)`,
            [randomUUID(), request.authUser!.id, id],
          );
        });
        communityEvents.emit(access.community.id, {
          type: "announcement.created",
          data: { id, ...input },
        });
        response.status(201).json({ data: { id } });
      } catch (error) {
        if (error instanceof z.ZodError)
          return next(
            new ApiProblem(
              422,
              "VALIDATION_ERROR",
              "Check the announcement.",
              z.flattenError(error).fieldErrors,
            ),
          );
        next(error);
      }
    },
  );

  router.get(
    "/:slug/events",
    requireCommunityAccess(database, "read"),
    async (_request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        const result = await database.query(
          `SELECT id, title, description, venue, starts_at, ends_at, status
           FROM community_events WHERE community_id = $1 ORDER BY starts_at DESC LIMIT 100`,
          [access.community.id],
        );
        response.json({ data: result.rows });
      } catch (error) {
        next(error);
      }
    },
  );

  router.post(
    "/:slug/events",
    requireCommunityAccess(database, "manage"),
    async (request, response, next) => {
      try {
        const input = eventSchema.parse(request.body);
        const access = response.locals.communityAccess as CommunityAccess;
        const id = randomUUID();
        await inTransaction(database, async (client) => {
          await client.query(
            `INSERT INTO community_events
            (id, community_id, title, description, venue, starts_at, ends_at, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
            [
              id,
              access.community.id,
              input.title,
              input.description,
              input.venue,
              input.startsAt,
              input.endsAt,
              request.authUser!.id,
            ],
          );
          await notifyCommunityMembers(client, access.community.id, {
            type: "community.event",
            title: access.community.name,
            body: input.title,
            href: `/app/communities/${access.community.slug}?tab=events`,
            exceptUserId: request.authUser!.id,
          });
        });
        communityEvents.emit(access.community.id, {
          type: "event.created",
          data: { id, ...input },
        });
        response.status(201).json({ data: { id } });
      } catch (error) {
        if (error instanceof z.ZodError)
          return next(
            new ApiProblem(
              422,
              "VALIDATION_ERROR",
              "Check the event.",
              z.flattenError(error).fieldErrors,
            ),
          );
        next(error);
      }
    },
  );

  router.get(
    "/:slug/members",
    requireCommunityAccess(database, "manage"),
    async (request, response, next) => {
      try {
        const access = response.locals.communityAccess as CommunityAccess;
        const status = z
          .enum(["pending", "active", "rejected", "suspended", "left"])
          .optional()
          .parse(request.query.status);
        const result = await database.query(
          `SELECT cm.id, cm.status, cm.is_primary, cm.joined_at,
                u.id AS user_id, u.full_name AS name, st.matric_number AS identifier,
                st.programme, st.academic_level AS level
           FROM community_memberships cm JOIN users u ON u.id = cm.user_id
           LEFT JOIN students st ON st.user_id = u.id
          WHERE cm.community_id = $1 AND ($2::text IS NULL OR cm.status = $2)
          ORDER BY cm.joined_at DESC`,
          [access.community.id, status ?? null],
        );
        response.json({ data: result.rows });
      } catch (error) {
        next(error);
      }
    },
  );

  router.patch(
    "/:slug/members/:membershipId",
    requireCommunityAccess(database, "manage"),
    async (request, response, next) => {
      try {
        const input = z
          .object({
            status: z.enum(["active", "rejected", "suspended", "left"]),
          })
          .parse(request.body);
        const access = response.locals.communityAccess as CommunityAccess;
        const updated = await database.query<{ id: string; user_id: string }>(
          `UPDATE community_memberships
            SET status = $1, approved_by = CASE WHEN $1 = 'active' THEN $2 ELSE approved_by END,
                approved_at = CASE WHEN $1 = 'active' THEN NOW() ELSE approved_at END,
                updated_at = NOW()
          WHERE id = $3 AND community_id = $4 RETURNING id, user_id`,
          [
            input.status,
            request.authUser!.id,
            request.params.membershipId,
            access.community.id,
          ],
        );
        if (!updated.rows.length)
          throw new ApiProblem(
            404,
            "MEMBERSHIP_NOT_FOUND",
            "The membership does not exist.",
          );
        await database.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id, metadata)
         VALUES ($1, $2, 'community.membership_updated', 'community_membership', $3, $4::jsonb)`,
          [
            randomUUID(),
            request.authUser!.id,
            request.params.membershipId,
            JSON.stringify({
              status: input.status,
              communityId: access.community.id,
            }),
          ],
        );
        response.json({
          data: { id: request.params.membershipId, status: input.status },
        });
      } catch (error) {
        if (error instanceof z.ZodError)
          return next(
            new ApiProblem(
              422,
              "VALIDATION_ERROR",
              "Select a valid membership status.",
            ),
          );
        next(error);
      }
    },
  );

  router.get(
    "/:slug/stream",
    requireCommunityAccess(database, "read"),
    (request, response) => {
      const access = response.locals.communityAccess as CommunityAccess;
      response.set({
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      });
      response.flushHeaders();
      response.write(
        `event: connected\ndata: ${JSON.stringify({ communityId: access.community.id })}\n\n`,
      );
      const push = (event: { type: string; data: unknown }) =>
        response.write(
          `event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`,
        );
      communityEvents.on(access.community.id, push);
      let checkingAccess = false;
      const heartbeat = setInterval(async () => {
        if (checkingAccess) return;
        checkingAccess = true;
        try {
          const currentAccess = await resolveAccess(
            database,
            request,
            access.community.id,
          );
          if (!currentAccess.canRead) {
            response.write("event: access.revoked\ndata: {}\n\n");
            clearInterval(heartbeat);
            communityEvents.off(access.community.id, push);
            response.end();
            return;
          }
          response.write(": keep-alive\n\n");
        } catch {
          clearInterval(heartbeat);
          communityEvents.off(access.community.id, push);
          response.end();
        } finally {
          checkingAccess = false;
        }
      }, 25_000);
      request.on("close", () => {
        clearInterval(heartbeat);
        communityEvents.off(access.community.id, push);
      });
    },
  );

  return router;
}

const communityAdminSchema = z.object({
  name: plainText(160),
  slug: z
    .string()
    .trim()
    .min(2)
    .max(120)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  type: z.enum(["unit", "campus_fellowship", "hostel_fellowship", "other"]),
  description: z.string().trim().max(10_000).default(""),
  requiresApproval: z.boolean().default(true),
  membersCanPost: z.boolean().default(true),
  chatEnabled: z.boolean().default(true),
});

export function adminCommunitiesRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));

  router.get(
    "/",
    requirePermission("community:manage"),
    async (_request, response, next) => {
      try {
        const [communities, counts] = await Promise.all([
          database.query<CommunityRow>(
            "SELECT * FROM communities ORDER BY type, name",
          ),
          database.query<{
            community_id: string;
            status: string;
            count: string;
          }>(
            "SELECT community_id, status, COUNT(*)::text AS count FROM community_memberships GROUP BY community_id, status",
          ),
        ]);
        const countFor = (communityId: string, status: string) =>
          Number(
            counts.rows.find(
              (row) =>
                row.community_id === communityId && row.status === status,
            )?.count ?? 0,
          );
        response.json({
          data: communities.rows.map((community) => ({
            ...community,
            member_count: countFor(community.id, "active"),
            pending_count: countFor(community.id, "pending"),
          })),
        });
      } catch (error) {
        next(error);
      }
    },
  );

  router.post(
    "/",
    requirePermission("community:manage"),
    async (request, response, next) => {
      try {
        const input = communityAdminSchema.parse(request.body);
        const id = randomUUID();
        await inTransaction(database, async (client) => {
          await client.query(
            `INSERT INTO communities
            (id, name, slug, type, description, requires_approval, members_can_post, chat_enabled, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
            [
              id,
              input.name,
              input.slug,
              input.type,
              input.description,
              input.requiresApproval,
              input.membersCanPost,
              input.chatEnabled,
              request.authUser!.id,
            ],
          );
          await client.query(
            "INSERT INTO conversations (id, community_id, type) VALUES ($1, $2, 'community')",
            [randomUUID(), id],
          );
          await client.query(
            `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'community.created', 'community', $3)`,
            [randomUUID(), request.authUser!.id, id],
          );
        });
        response.status(201).json({ data: { id, ...input } });
      } catch (error) {
        if (error instanceof z.ZodError)
          return next(
            new ApiProblem(
              422,
              "VALIDATION_ERROR",
              "Check the community details.",
              z.flattenError(error).fieldErrors,
            ),
          );
        if (
          typeof error === "object" &&
          error &&
          "code" in error &&
          error.code === "23505"
        )
          return next(
            new ApiProblem(
              409,
              "COMMUNITY_EXISTS",
              "A community already uses that name or slug.",
            ),
          );
        next(error);
      }
    },
  );

  router.patch(
    "/:id",
    requirePermission("community:manage"),
    async (request, response, next) => {
      try {
        const input = communityAdminSchema
          .partial()
          .extend({ status: z.enum(["active", "inactive"]).optional() })
          .parse(request.body);
        const current = await database.query<CommunityRow>(
          "SELECT * FROM communities WHERE id = $1",
          [request.params.id],
        );
        if (!current.rows[0])
          throw new ApiProblem(
            404,
            "COMMUNITY_NOT_FOUND",
            "The community does not exist.",
          );
        const nextValue = {
          name: input.name ?? current.rows[0].name,
          slug: input.slug ?? current.rows[0].slug,
          type: input.type ?? current.rows[0].type,
          description: input.description ?? current.rows[0].description,
          status: input.status ?? current.rows[0].status,
          requiresApproval:
            input.requiresApproval ?? current.rows[0].requires_approval,
          membersCanPost:
            input.membersCanPost ?? current.rows[0].members_can_post,
          chatEnabled: input.chatEnabled ?? current.rows[0].chat_enabled,
        };
        await database.query(
          `UPDATE communities SET name = $1, slug = $2, type = $3, description = $4,
                status = $5, requires_approval = $6, members_can_post = $7,
                chat_enabled = $8, updated_at = NOW() WHERE id = $9`,
          [
            nextValue.name,
            nextValue.slug,
            nextValue.type,
            nextValue.description,
            nextValue.status,
            nextValue.requiresApproval,
            nextValue.membersCanPost,
            nextValue.chatEnabled,
            request.params.id,
          ],
        );
        await database.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id, metadata)
         VALUES ($1, $2, 'community.updated', 'community', $3, $4::jsonb)`,
          [
            randomUUID(),
            request.authUser!.id,
            request.params.id,
            JSON.stringify(input),
          ],
        );
        response.json({ data: { id: request.params.id, ...nextValue } });
      } catch (error) {
        if (error instanceof z.ZodError)
          return next(
            new ApiProblem(
              422,
              "VALIDATION_ERROR",
              "Check the community details.",
            ),
          );
        next(error);
      }
    },
  );

  return router;
}

export function adminLeadershipRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));
  router.use(requirePermission("leadership:manage"));

  router.get("/positions", async (_request, response, next) => {
    try {
      const result = await database.query(
        "SELECT id, name, scope_type, capabilities FROM leadership_positions ORDER BY scope_type, name",
      );
      response.json({ data: result.rows });
    } catch (error) {
      next(error);
    }
  });

  router.get("/", async (_request, response, next) => {
    try {
      const result = await database.query(
        `SELECT la.id, lp.id AS position_id, lp.name AS position, lp.scope_type,
                la.user_id, COALESCE(u.full_name, la.assignee_name) AS leader_name,
                c.id AS community_id, c.name AS community_name, c.slug AS community_slug,
                la.starts_at, la.ends_at, la.active
           FROM leadership_assignments la JOIN leadership_positions lp ON lp.id = la.position_id
           LEFT JOIN users u ON u.id = la.user_id LEFT JOIN communities c ON c.id = la.community_id
          ORDER BY la.active DESC, c.name NULLS FIRST, lp.name`,
      );
      response.json({ data: result.rows });
    } catch (error) {
      next(error);
    }
  });

  router.post("/assign", async (request, response, next) => {
    try {
      const input = z
        .object({
          positionId: z.string().uuid(),
          userId: z.string().uuid().nullable().optional(),
          assigneeName: plainText(160).nullable().optional(),
          communityId: z.string().uuid().nullable().optional(),
          startsAt: z.string().datetime().optional(),
        })
        .refine((value) => value.userId || value.assigneeName, {
          message: "Select a user or provide the assignee name.",
        })
        .parse(request.body);
      const position = await database.query<{ scope_type: string }>(
        "SELECT scope_type FROM leadership_positions WHERE id = $1",
        [input.positionId],
      );
      if (!position.rows[0])
        throw new ApiProblem(
          404,
          "POSITION_NOT_FOUND",
          "The leadership position does not exist.",
        );
      if (position.rows[0].scope_type === "community" && !input.communityId)
        throw new ApiProblem(
          422,
          "COMMUNITY_REQUIRED",
          "Select the community for this position.",
        );
      const id = randomUUID();
      await inTransaction(database, async (client) => {
        await client.query(
          `UPDATE leadership_assignments SET active = FALSE, ends_at = NOW()
            WHERE position_id = $1
              AND (community_id = $2 OR (community_id IS NULL AND $2::uuid IS NULL))
              AND active = TRUE`,
          [input.positionId, input.communityId ?? null],
        );
        await client.query(
          `INSERT INTO leadership_assignments
            (id, position_id, user_id, assignee_name, community_id, starts_at, assigned_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7)`,
          [
            id,
            input.positionId,
            input.userId ?? null,
            input.assigneeName ?? null,
            input.communityId ?? null,
            input.startsAt ?? new Date().toISOString(),
            request.authUser!.id,
          ],
        );
        if (input.userId && input.communityId) {
          await client.query(
            `INSERT INTO community_memberships (id, community_id, user_id, status, approved_at, approved_by)
             VALUES ($1, $2, $3, 'active', NOW(), $4)
             ON CONFLICT (user_id, community_id) DO UPDATE
               SET status = 'active', approved_at = NOW(), approved_by = EXCLUDED.approved_by, updated_at = NOW()`,
            [
              randomUUID(),
              input.communityId,
              input.userId,
              request.authUser!.id,
            ],
          );
        }
        await client.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id, metadata)
           VALUES ($1, $2, 'leadership.transferred', 'leadership_assignment', $3, $4::jsonb)`,
          [
            randomUUID(),
            request.authUser!.id,
            id,
            JSON.stringify({
              positionId: input.positionId,
              communityId: input.communityId,
              userId: input.userId,
            }),
          ],
        );
      });
      response.status(201).json({ data: { id } });
    } catch (error) {
      if (error instanceof z.ZodError)
        return next(
          new ApiProblem(
            422,
            "VALIDATION_ERROR",
            "Check the leadership assignment.",
            z.flattenError(error).fieldErrors,
          ),
        );
      next(error);
    }
  });

  return router;
}

export function adminAccountsRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));
  router.use(requirePermission("leadership:manage"));
  router.post("/", async (request, response, next) => {
    try {
      const input = z
        .object({
          username: z
            .string()
            .trim()
            .min(3)
            .max(80)
            .regex(/^[a-zA-Z0-9._-]+$/),
          email: z.string().trim().email().max(320),
          name: plainText(160),
          primaryRole: z
            .enum([
              "super_admin",
              "chapel_admin",
              "pastor",
              "worker",
              "attendance_usher",
              "member",
            ])
            .default("member"),
          globalRoles: z.array(z.enum(roles)).max(8).default([]),
        })
        .parse(request.body);
      const userId = randomUUID();
      const setupToken = createOpaqueToken();
      await inTransaction(database, async (client) => {
        await client.query(
          `INSERT INTO users (id, username, email, password_hash, full_name, role, status)
           VALUES ($1, $2, $3, $4, $5, $6, 'inactive')`,
          [
            userId,
            input.username.toLowerCase(),
            input.email.toLowerCase(),
            await hashPassword(createOpaqueToken()),
            input.name,
            input.primaryRole,
          ],
        );
        for (const role of input.globalRoles) {
          await client.query(
            `INSERT INTO user_global_roles (id, user_id, role_key, assigned_by)
             VALUES ($1, $2, $3, $4) ON CONFLICT (user_id, role_key) DO NOTHING`,
            [randomUUID(), userId, role, request.authUser!.id],
          );
        }
        await client.query(
          `INSERT INTO account_setup_tokens (id, user_id, token_hash, expires_at, created_by)
           VALUES ($1, $2, $3, NOW() + INTERVAL '24 hours', $4)`,
          [
            randomUUID(),
            userId,
            hashToken(setupToken, config.CHAPELFLOW_SESSION_SECRET),
            request.authUser!.id,
          ],
        );
        await client.query(
          `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'account.provisioned', 'user', $3)`,
          [randomUUID(), request.authUser!.id, userId],
        );
      });
      response.status(201).json({
        data: {
          userId,
          setupRequired: true,
          setupPath: `/reset-password?setup=${encodeURIComponent(setupToken)}`,
          expiresInHours: 24,
        },
      });
    } catch (error) {
      if (error instanceof z.ZodError)
        return next(
          new ApiProblem(
            422,
            "VALIDATION_ERROR",
            "Check the account details.",
            z.flattenError(error).fieldErrors,
          ),
        );
      if (
        typeof error === "object" &&
        error &&
        "code" in error &&
        error.code === "23505"
      )
        return next(
          new ApiProblem(
            409,
            "ACCOUNT_EXISTS",
            "An account already uses that email or username.",
          ),
        );
      next(error);
    }
  });
  return router;
}
