import { PGlite, type Results, type Transaction } from "@electric-sql/pglite";
import { resolve } from "node:path";
import { Pool, type QueryResult, type QueryResultRow } from "pg";

export interface DatabaseClient {
  query<T extends QueryResultRow = QueryResultRow>(
    text: string,
    values?: unknown[],
  ): Promise<QueryResult<T>>;
  exec?(text: string): Promise<void>;
  release(): void;
}

export interface Database {
  query<T extends QueryResultRow = QueryResultRow>(
    text: string,
    values?: unknown[],
  ): Promise<QueryResult<T>>;
  connect?(): Promise<DatabaseClient>;
  transaction?<T>(work: (client: DatabaseClient) => Promise<T>): Promise<T>;
  end(): Promise<void>;
}

function toQueryResult<T extends QueryResultRow>(result: Results<T>): QueryResult<T> {
  return {
    command: result.command ?? "",
    rowCount: result.rowCount ?? result.affectedRows ?? result.rows.length,
    oid: 0,
    fields: [],
    rows: result.rows,
  };
}

function pgliteClient(client: PGlite | Transaction): DatabaseClient {
  return {
    async query<T extends QueryResultRow>(text: string, values?: unknown[]) {
      return toQueryResult(await client.query<T>(text, values));
    },
    async exec(text: string) {
      await client.exec(text);
    },
    release() {},
  };
}

export function createDatabase(connectionString: string): Database {
  if (connectionString.startsWith("pglite://")) {
    const configuredPath = connectionString.slice("pglite://".length);
    const dataDirectory = configuredPath === "memory" ? "memory://" : resolve(process.cwd(), configuredPath);
    const instance = new PGlite(dataDirectory);
    const client = pgliteClient(instance);
    return {
      query: client.query,
      transaction: (work) => instance.transaction((transaction) => work(pgliteClient(transaction))),
      end: () => instance.close(),
    };
  }

  return new Pool({
    connectionString,
    max: 12,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
    ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: true } : undefined,
  }) as Database;
}

export async function inTransaction<T>(database: Database, work: (client: DatabaseClient) => Promise<T>) {
  if (database.transaction) return database.transaction(work);
  if (!database.connect) throw new Error("The database does not support transactions.");

  const client = await database.connect();
  try {
    await client.query("BEGIN");
    const result = await work(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
