import { randomUUID } from "node:crypto";
import { Router } from "express";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { inTransaction } from "./db.js";
import { ApiProblem, authenticate, requirePermission } from "./http.js";

const chapelAnnouncementSchema = z.object({
  title: z.string().trim().min(1).max(180),
  content: z
    .string()
    .trim()
    .min(1)
    .max(10_000)
    .refine((value) => !/<\/?[a-z][^>]*>/i.test(value), "HTML is not allowed."),
  priority: z.enum(["normal", "important", "urgent"]).default("normal"),
  expiresAt: z.string().datetime().nullable().optional(),
});

export function notificationsRouter(database: Database, config: AppConfig) {
  const router = Router();
  router.use(authenticate(database, config));

  router.get("/", async (request, response, next) => {
    try {
      const result = await database.query(
        `SELECT id, community_id, type, title, body, href, read_at, created_at
           FROM notifications WHERE user_id = $1
          ORDER BY read_at NULLS FIRST, created_at DESC LIMIT 100`,
        [request.authUser!.id],
      );
      response.json({ data: result.rows });
    } catch (error) {
      next(error);
    }
  });

  router.patch("/:id/read", async (request, response, next) => {
    try {
      const result = await database.query<{ id: string }>(
        "UPDATE notifications SET read_at = NOW() WHERE id = $1 AND user_id = $2 RETURNING id",
        [request.params.id, request.authUser!.id],
      );
      if (!result.rows.length)
        throw new ApiProblem(
          404,
          "NOTIFICATION_NOT_FOUND",
          "The notification does not exist.",
        );
      response.status(204).end();
    } catch (error) {
      next(error);
    }
  });

  return router;
}

export function chapelAnnouncementsRouter(
  database: Database,
  config: AppConfig,
) {
  const router = Router();
  router.use(authenticate(database, config));

  router.get("/", async (_request, response, next) => {
    try {
      const result = await database.query(
        `SELECT a.id, a.title, a.content, a.priority, a.published_at, a.expires_at,
                u.full_name AS author_name
           FROM announcements a JOIN users u ON u.id = a.author_id
          WHERE a.community_id IS NULL AND a.published_at <= NOW()
            AND (a.expires_at IS NULL OR a.expires_at > NOW())
          ORDER BY a.published_at DESC LIMIT 100`,
      );
      response.json({ data: result.rows });
    } catch (error) {
      next(error);
    }
  });

  router.post(
    "/",
    requirePermission("chapel:announce"),
    async (request, response, next) => {
      try {
        const input = chapelAnnouncementSchema.parse(request.body);
        const id = randomUUID();
        await inTransaction(database, async (client) => {
          await client.query(
            `INSERT INTO announcements
            (id, community_id, author_id, title, content, priority, expires_at)
           VALUES ($1, NULL, $2, $3, $4, $5, $6)`,
            [
              id,
              request.authUser!.id,
              input.title,
              input.content,
              input.priority,
              input.expiresAt ?? null,
            ],
          );
          const users = await client.query<{ id: string }>(
            "SELECT id FROM users WHERE status = 'active'",
          );
          for (const user of users.rows) {
            if (user.id === request.authUser!.id) continue;
            await client.query(
              `INSERT INTO notifications (id, user_id, type, title, body, href)
             VALUES ($1, $2, 'chapel.announcement', $3, $4, '/app')`,
              [randomUUID(), user.id, input.title, input.content.slice(0, 240)],
            );
          }
          await client.query(
            `INSERT INTO audit_events (id, actor_user_id, action, entity_type, entity_id)
           VALUES ($1, $2, 'chapel.announcement_created', 'announcement', $3)`,
            [randomUUID(), request.authUser!.id, id],
          );
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

  return router;
}
