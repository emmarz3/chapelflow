// @vitest-environment node
import { readFile } from "node:fs/promises";
import type { NextFunction, Request, Response } from "express";
import { describe, expect, it, vi } from "vitest";
import type { AppConfig } from "./config.js";
import { requireTrustedOrigin } from "./http.js";
import {
  hashPassword,
  signQrToken,
  verifyPassword,
  verifyQrToken,
} from "./security.js";

describe("attendance security primitives", () => {
  it("accepts loopback port changes only outside production", () => {
    const request = {
      method: "POST",
      get: () => "http://127.0.0.1:5176",
    } as unknown as Request;
    const developmentNext = vi.fn() as unknown as NextFunction;
    const productionNext = vi.fn() as unknown as NextFunction;
    const baseConfig = {
      APP_ORIGIN: "http://localhost:5173",
    } as AppConfig;

    requireTrustedOrigin({ ...baseConfig, NODE_ENV: "development" })(
      request,
      {} as Response,
      developmentNext,
    );
    requireTrustedOrigin({ ...baseConfig, NODE_ENV: "production" })(
      request,
      {} as Response,
      productionNext,
    );

    expect(developmentNext).toHaveBeenCalledWith();
    expect(productionNext).toHaveBeenCalledWith(
      expect.objectContaining({ code: "UNTRUSTED_ORIGIN" }),
    );
  });

  it("hashes passwords and rejects the wrong password", async () => {
    const hash = await hashPassword("secure-password-1");
    expect(hash).not.toContain("secure-password-1");
    await expect(verifyPassword("secure-password-1", hash)).resolves.toBe(true);
    await expect(verifyPassword("wrong-password", hash)).resolves.toBe(false);
  });

  it("rejects malformed, forged, and expired QR tokens", () => {
    const secret = "test-signing-secret-that-is-long-enough";
    const token = signQrToken(
      { passId: "pass-id", sessionId: "session-id" },
      secret,
      60,
    );
    expect(verifyQrToken(token, secret)).toMatchObject({
      passId: "pass-id",
      sessionId: "session-id",
    });
    expect(verifyQrToken(`${token}x`, secret)).toBeNull();
    expect(verifyQrToken("not-a-token", secret)).toBeNull();
    const expired = signQrToken(
      { passId: "pass-id", sessionId: "session-id" },
      secret,
      -1,
    );
    expect(verifyQrToken(expired, secret)).toBeNull();
  });

  it("keeps database-level race protection in the attendance migration", async () => {
    const migration = await readFile(
      new URL("./migrations/001_attendance_core.sql", import.meta.url),
      "utf8",
    );
    expect(migration).toContain("UNIQUE (attendance_session_id, student_id)");
    expect(migration).toContain(
      "UNIQUE (recorded_by_usher_id, idempotency_key)",
    );
  });
});
