import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { createDatabase } from "./db.js";
import { runMigrations } from "./migrations.js";
import { seedOrganization } from "./organization-seed.js";

const config = loadConfig();
const database = createDatabase(config.DATABASE_URL);
if (config.NODE_ENV === "development") {
  await runMigrations(database);
  await seedOrganization(database);
}
const app = createApp(database, config);
const server = app.listen(config.PORT, "0.0.0.0", () => {
  console.log(`ChapelFlow API listening on port ${config.PORT}`);
});

async function shutdown() {
  server.close(async () => {
    await database.end();
    process.exit(0);
  });
}

process.on("SIGTERM", () => void shutdown());
process.on("SIGINT", () => void shutdown());
