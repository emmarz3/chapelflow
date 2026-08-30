import { randomUUID } from "node:crypto";
import type { Database } from "./db.js";
import { hashPassword } from "./security.js";

interface UsherSeed {
  username: string;
  password: string;
  name: string;
  email: string;
}

function seedValues(environment: NodeJS.ProcessEnv): UsherSeed[] {
  const values = [
    { number: "01", username: environment.CHAPELFLOW_USHER_01_USERNAME, password: environment.CHAPELFLOW_USHER_01_PASSWORD },
    { number: "02", username: environment.CHAPELFLOW_USHER_02_USERNAME, password: environment.CHAPELFLOW_USHER_02_PASSWORD },
  ];
  if (values.some((value) => !value.username || !value.password)) {
    throw new Error("Both usher usernames and passwords must be configured before seeding.");
  }
  return values.map((value) => ({
    username: value.username!.trim().toLowerCase(),
    password: value.password!,
    name: `Attendance Usher ${value.number}`,
    email: `${value.username!.trim().toLowerCase()}@ushers.chapelflow.local`,
  }));
}

export async function seedUshers(database: Database, environment: NodeJS.ProcessEnv = process.env) {
  const ushers = seedValues(environment);
  if (new Set(ushers.map((usher) => usher.username)).size !== 2) {
    throw new Error("The two seeded usher usernames must be different.");
  }
  for (const usher of ushers) {
    const existing = await database.query<{ role: string }>("SELECT role FROM users WHERE username = $1", [usher.username]);
    if (existing.rows[0]) {
      if (existing.rows[0].role !== "attendance_usher") {
        throw new Error(`Configured username ${usher.username} belongs to a different role.`);
      }
      continue;
    }
    await database.query(
      `INSERT INTO users (id, username, email, password_hash, full_name, role, status)
       VALUES ($1, $2, $3, $4, $5, 'attendance_usher', 'active')`,
      [randomUUID(), usher.username, usher.email, await hashPassword(usher.password), usher.name],
    );
  }
}

export async function seedAdministrator(
  database: Database,
  environment: NodeJS.ProcessEnv = process.env,
) {
  const username = environment.CHAPELFLOW_ADMIN_USERNAME?.trim().toLowerCase();
  const email = environment.CHAPELFLOW_ADMIN_EMAIL?.trim().toLowerCase();
  const password = environment.CHAPELFLOW_ADMIN_PASSWORD;
  const name = environment.CHAPELFLOW_ADMIN_NAME?.trim();
  if (!username || !email || !password || !name) {
    throw new Error("The initial administrator username, email, name, and password must be configured before seeding.");
  }
  const existing = await database.query<{ role: string }>(
    "SELECT role FROM users WHERE username = $1 OR email = $2",
    [username, email],
  );
  if (existing.rows[0]) {
    if (existing.rows[0].role !== "super_admin") {
      throw new Error("The configured administrator identity belongs to a non-administrator account.");
    }
    return;
  }
  await database.query(
    `INSERT INTO users (id, username, email, password_hash, full_name, role, status)
     VALUES ($1, $2, $3, $4, $5, 'super_admin', 'active')`,
    [randomUUID(), username, email, await hashPassword(password), name],
  );
}
