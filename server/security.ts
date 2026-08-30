import {
  createHash,
  createHmac,
  randomBytes,
  scrypt as scryptCallback,
  timingSafeEqual,
} from "node:crypto";
import { promisify } from "node:util";

const scrypt = promisify(scryptCallback);

export async function hashPassword(password: string) {
  const salt = randomBytes(16);
  const derived = (await scrypt(password, salt, 64)) as Buffer;
  return `scrypt$${salt.toString("base64url")}$${derived.toString("base64url")}`;
}

export async function verifyPassword(password: string, encoded: string) {
  const [algorithm, saltValue, hashValue] = encoded.split("$");
  if (algorithm !== "scrypt" || !saltValue || !hashValue) return false;
  const expected = Buffer.from(hashValue, "base64url");
  const actual = (await scrypt(password, Buffer.from(saltValue, "base64url"), expected.length)) as Buffer;
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

export function createOpaqueToken(bytes = 32) {
  return randomBytes(bytes).toString("base64url");
}

export function hashToken(token: string, secret: string) {
  return createHash("sha256").update(secret).update(token).digest("hex");
}

interface QrClaims {
  v: 1;
  passId: string;
  sessionId: string;
  issuedAt: number;
  expiresAt: number;
}

export function signQrToken(
  claims: Omit<QrClaims, "v" | "issuedAt" | "expiresAt">,
  secret: string,
  lifetimeSeconds = 120,
) {
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = Buffer.from(
    JSON.stringify({ v: 1, ...claims, issuedAt, expiresAt: issuedAt + lifetimeSeconds }),
  ).toString("base64url");
  const signature = createHmac("sha256", secret).update(payload).digest("base64url");
  return `cf1.${payload}.${signature}`;
}

export function verifyQrToken(token: string, secret: string): QrClaims | null {
  const [prefix, payload, signature] = token.split(".");
  if (prefix !== "cf1" || !payload || !signature) return null;
  const expected = createHmac("sha256", secret).update(payload).digest();
  const actual = Buffer.from(signature, "base64url");
  if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) return null;
  try {
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as Partial<QrClaims>;
    if (
      claims.v !== 1 ||
      typeof claims.passId !== "string" ||
      typeof claims.sessionId !== "string" ||
      typeof claims.expiresAt !== "number" ||
      claims.expiresAt < Math.floor(Date.now() / 1000)
    ) return null;
    return claims as QrClaims;
  } catch {
    return null;
  }
}
