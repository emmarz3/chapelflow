import { loadConfig } from "../config.js";
import { createDatabase } from "../db.js";
import { runMigrations } from "../migrations.js";
import { seedOrganization } from "../organization-seed.js";

const config = loadConfig();
const database = createDatabase(config.DATABASE_URL);
await runMigrations(database);
await seedOrganization(database);
await database.end();
console.log("ChapelFlow organization seed completed.");
