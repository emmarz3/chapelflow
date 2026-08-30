import { randomUUID } from "node:crypto";
import cookieParser from "cookie-parser";
import express from "express";
import rateLimit from "express-rate-limit";
import helmet from "helmet";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import { attendanceRouter } from "./attendance.js";
import { authRouter } from "./auth.js";
import { dashboardRouter } from "./dashboard.js";
import { errorHandler, requireTrustedOrigin } from "./http.js";
import { membersRouter } from "./members.js";
import {
  adminAccountsRouter,
  adminCommunitiesRouter,
  adminLeadershipRouter,
  communitiesRouter,
  publicCommunitiesRouter,
} from "./communities.js";
import {
  chapelAnnouncementsRouter,
  notificationsRouter,
} from "./notifications.js";

export function createApp(database: Database, config: AppConfig) {
  const app = express();
  if (config.NODE_ENV === "production") app.set("trust proxy", 1);
  app.disable("x-powered-by");
  app.use(helmet({ contentSecurityPolicy: false }));
  app.use(express.json({ limit: "32kb" }));
  app.use(cookieParser());
  app.use((request, response, next) => {
    const requestId =
      request.get("x-request-id")?.slice(0, 100) || randomUUID();
    response.locals.requestId = requestId;
    response.set("x-request-id", requestId);
    next();
  });
  app.use(requireTrustedOrigin(config));
  app.get("/api/health", async (_request, response, next) => {
    try {
      await database.query("SELECT 1");
      response.json({ status: "ok" });
    } catch (error) {
      next(error);
    }
  });
  app.use(
    "/api/auth",
    rateLimit({
      windowMs: 15 * 60_000,
      limit: 60,
      standardHeaders: "draft-8",
      legacyHeaders: false,
    }),
    authRouter(database, config),
  );
  app.use("/api/dashboard", dashboardRouter(database, config));
  app.use("/api/members", membersRouter(database, config));
  app.use("/api/public/communities", publicCommunitiesRouter(database));
  app.use("/api/communities", communitiesRouter(database, config));
  app.use("/api/admin/communities", adminCommunitiesRouter(database, config));
  app.use("/api/admin/leadership", adminLeadershipRouter(database, config));
  app.use("/api/admin/accounts", adminAccountsRouter(database, config));
  app.use("/api/notifications", notificationsRouter(database, config));
  app.use(
    "/api/chapel-announcements",
    chapelAnnouncementsRouter(database, config),
  );
  app.use(
    "/api/attendance",
    rateLimit({
      windowMs: 60_000,
      limit: 180,
      standardHeaders: "draft-8",
      legacyHeaders: false,
    }),
    attendanceRouter(database, config),
  );
  app.use("/api", (_request, response) =>
    response.status(404).json({
      code: "NOT_FOUND",
      message: "The requested API endpoint does not exist.",
      requestId: response.locals.requestId,
    }),
  );
  app.use(errorHandler);
  return app;
}
