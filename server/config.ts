import { z } from "zod";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const environmentFile = resolve(process.cwd(), ".env");
if (existsSync(environmentFile)) process.loadEnvFile(environmentFile);

const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().min(1).max(65_535).default(8000),
  DATABASE_URL: z.string().min(1),
  APP_ORIGIN: z.string().url(),
  CHAPELFLOW_SESSION_SECRET: z.string().min(32),
  CHAPELFLOW_QR_SIGNING_SECRET: z.string().min(32),
});

export type AppConfig = z.infer<typeof schema>;

export function loadConfig(environment: NodeJS.ProcessEnv = process.env): AppConfig {
  const isProduction = environment.NODE_ENV === "production";
  const localDefaults: NodeJS.ProcessEnv = isProduction
    ? {}
    : {
        DATABASE_URL: "pglite://.chapelflow-data",
        APP_ORIGIN: "http://localhost:5173",
        CHAPELFLOW_SESSION_SECRET: "chapelflow-local-session-secret-change-me",
        CHAPELFLOW_QR_SIGNING_SECRET: "chapelflow-local-qr-signing-secret-change-me",
      };
  const parsed = schema.safeParse({ ...localDefaults, ...environment });
  if (!parsed.success) {
    const names = parsed.error.issues.map((issue) => issue.path.join(".")).join(", ");
    throw new Error(`Invalid server configuration: ${names}`);
  }
  return parsed.data;
}
