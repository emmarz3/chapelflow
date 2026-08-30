import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { Database } from "./db.js";
import { inTransaction } from "./db.js";

const migrations = [
  "001_attendance_core.sql",
  "002_pending_student_approval.sql",
  "003_community_engine.sql",
];

export async function runMigrations(database: Database) {
  await database.query(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      name TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `);
  const directory = join(dirname(fileURLToPath(import.meta.url)), "migrations");
  for (const name of migrations) {
    const applied = await database.query(
      "SELECT 1 FROM schema_migrations WHERE name = $1",
      [name],
    );
    if (applied.rows.length) continue;
    await inTransaction(database, async (client) => {
      const sql = await readFile(join(directory, name), "utf8");
      if (client.exec) await client.exec(sql);
      else await client.query(sql);
      await client.query(
        "INSERT INTO schema_migrations (name) VALUES ($1) ON CONFLICT DO NOTHING",
        [name],
      );
    });
  }
}
