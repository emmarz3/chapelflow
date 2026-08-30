import { loadConfig } from "../config.js";
import { createDatabase } from "../db.js";
import { seedAdministrator, seedUshers } from "../seed.js";

const config = loadConfig();
const database = createDatabase(config.DATABASE_URL);
try {
  await seedAdministrator(database);
  await seedUshers(database);
  console.log("Initial administrator and attendance usher accounts are ready.");
} finally {
  await database.end();
}
