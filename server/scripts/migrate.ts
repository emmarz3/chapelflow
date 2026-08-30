import { loadConfig } from "../config.js";
import { createDatabase } from "../db.js";
import { runMigrations } from "../migrations.js";

const config = loadConfig();
const database = createDatabase(config.DATABASE_URL);
try {
  await runMigrations(database);
  console.log("Database migrations completed.");
} finally {
  await database.end();
}
