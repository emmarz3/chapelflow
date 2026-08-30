import type {
  ErrorRequestHandler,
  NextFunction,
  Request,
  Response,
} from "express";
import type { AppConfig } from "./config.js";
import type { Database } from "./db.js";
import {
  rolesHavePermission,
  type Role,
  type ServerPermission,
} from "./permissions.js";
import { hashToken } from "./security.js";

export class ApiProblem extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fieldErrors?: Record<string, string[]>,
  ) {
    super(message);
  }
}

export function requireTrustedOrigin(config: AppConfig) {
  return (request: Request, _response: Response, next: NextFunction) => {
    if (["GET", "HEAD", "OPTIONS"].includes(request.method)) return next();
    const origin = request.get("origin");
    const isTrustedDevelopmentOrigin =
      config.NODE_ENV !== "production" &&
      isLoopbackOrigin(origin) &&
      isLoopbackOrigin(config.APP_ORIGIN);
    if (origin && origin !== config.APP_ORIGIN && !isTrustedDevelopmentOrigin) {
      return next(
        new ApiProblem(
          403,
          "UNTRUSTED_ORIGIN",
          "The request origin is not allowed.",
        ),
      );
    }
    next();
  };
}

function isLoopbackOrigin(value: string | undefined) {
  if (!value) return false;
  try {
    const url = new URL(value);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
    );
  } catch {
    return false;
  }
}

export function authenticate(database: Database, config: AppConfig) {
  return async (request: Request, _response: Response, next: NextFunction) => {
    try {
      const token = request.cookies.chapelflow_session as string | undefined;
      if (!token)
        throw new ApiProblem(
          401,
          "AUTHENTICATION_REQUIRED",
          "Sign in to continue.",
        );
      const result = await database.query<{
        id: string;
        username: string;
        email: string;
        full_name: string;
        role: Role;
      }>(
        `SELECT u.id, u.username, u.email, u.full_name, u.role
           FROM auth_sessions s
           JOIN users u ON u.id = s.user_id
          WHERE s.token_hash = $1 AND s.expires_at > NOW() AND u.status = 'active'`,
        [hashToken(token, config.CHAPELFLOW_SESSION_SECRET)],
      );
      const user = result.rows[0];
      if (!user)
        throw new ApiProblem(
          401,
          "SESSION_EXPIRED",
          "Your session has expired.",
        );
      request.authSessionToken = token;
      request.authUser = {
        id: user.id,
        username: user.username,
        email: user.email,
        name: user.full_name,
        role: user.role,
        roles: [user.role],
      };
      const assignedRoles = await database.query<{ role_key: Role }>(
        "SELECT role_key FROM user_global_roles WHERE user_id = $1",
        [user.id],
      );
      request.authUser.roles = Array.from(
        new Set([user.role, ...assignedRoles.rows.map((row) => row.role_key)]),
      );
      next();
    } catch (error) {
      next(error);
    }
  };
}

export function requirePermission(permission: ServerPermission) {
  return (request: Request, _response: Response, next: NextFunction) => {
    if (!request.authUser)
      return next(
        new ApiProblem(401, "AUTHENTICATION_REQUIRED", "Sign in to continue."),
      );
    if (!rolesHavePermission(request.authUser.roles, permission)) {
      return next(
        new ApiProblem(
          403,
          "ACCESS_DENIED",
          "You do not have permission to perform this action.",
        ),
      );
    }
    next();
  };
}

export const errorHandler: ErrorRequestHandler = (
  error,
  request,
  response,
  _next,
) => {
  void _next;
  const requestId = String(response.locals.requestId ?? "");
  if (error instanceof ApiProblem) {
    response.status(error.status).json({
      code: error.code,
      message: error.message,
      fieldErrors: error.fieldErrors,
      requestId,
    });
    return;
  }
  if (error instanceof SyntaxError && "body" in error) {
    response.status(400).json({
      code: "INVALID_JSON",
      message: "The request body is invalid.",
      requestId,
    });
    return;
  }
  console.error("Unhandled API error", {
    requestId,
    method: request.method,
    path: request.path,
  });
  response.status(500).json({
    code: "INTERNAL_ERROR",
    message: "The request could not be completed.",
    requestId,
  });
};
